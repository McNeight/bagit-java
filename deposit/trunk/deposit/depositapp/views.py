from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.views import login as base_login, logout_then_login
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.views.generic.create_update import create_object

import deposit.depositapp.forms as forms
import deposit.depositapp.models as models
from deposit.depositapp.queries import TransferQuery


def index(request):
    if request.user.is_authenticated():
        return HttpResponseRedirect(reverse('user_url',
                args=[request.user.username]))
    return HttpResponseRedirect(reverse('login_url'))

def login(request, redirect_field_name=REDIRECT_FIELD_NAME):
    if request.method == 'POST':
        request.POST = request.POST.__copy__()
        request.POST[redirect_field_name] = reverse('overview_url',
                args=[request.POST['username']])
    return base_login(request, "login.html",  redirect_field_name)

def logout(request):
    return logout_then_login(request, login_url=reverse('login_url'))

def overview(request, username):    
    try:
        deposit_user = models.User.objects.get(username=username)
        user = deposit_user
        user_form_class = forms.DepositUserForm
    except models.User.DoesNotExist:
        deposit_user = None
        try:
            user = User.objects.get(username=username)
            user_form_class = forms.UserForm
        except User.DoesNotExist:
            raise Http404
    if request.user.is_authenticated() and request.user.username == username:
        is_user = True
        password_form = PasswordChangeForm(request.user)
        user_form = user_form_class(instance=user)            
    else:
        is_user = False
        password_form = None
        user_form = None
    q = TransferQuery()
    q.include_received=False
    return render_to_response('overview.html', {'deposit_user': deposit_user,
            'user':user, 'is_user':is_user, 'projects':models.Project.objects.all(),
            'password_form':password_form, 'user_form':user_form, 'query':q},
            context_instance=RequestContext(request))

def user(request, username, command = None):    
    try:
        deposit_user = models.User.objects.get(username=username)
        user = deposit_user
        user_form_class = forms.DepositUserForm
    except models.User.DoesNotExist:
        deposit_user = None
        try:
            user = User.objects.get(username=username)
            user_form_class = forms.UserForm
        except User.DoesNotExist:
            raise Http404
    if request.user.is_authenticated() and request.user.username == username:
        is_user = True
        if command == "password" and request.method == "POST":
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                request.user.message_set.create(
                        message="Your password was changed.")
                return HttpResponseRedirect(reverse('user_url',
                        args=[user.username]))
        elif command == "update" and request.method == "POST":
            user_form = user_form_class(request.POST, instance=user)
            if user_form.is_valid():
                user_form.save()
                request.user.message_set.create(
                        message="Your information has been updated.")
                return HttpResponseRedirect(reverse('user_url',
                        args=[user.username]))
        else:
            password_form = PasswordChangeForm(request.user)
            user_form = user_form_class(instance=user)            
    else:
        is_user = False
        password_form = None
        user_form = None
    q = TransferQuery()
    q.include_received=False
    return render_to_response('user.html', {'deposit_user': deposit_user,
            'user':user, 'is_user':is_user, 'projects':models.Project.objects.all(),
            'password_form':password_form, 'user_form':user_form, 'query':q},
            context_instance=RequestContext(request))

def transfer(request, transfer_id):
    if not request.user.is_authenticated():
        return HttpResponseForbidden()
    if request.method == 'POST':
        return HttpResponseNotAllowed()
    trans = get_object_or_404(models.Transfer, id=transfer_id)
    transfer_class = getattr(models, trans.transfer_type)
    transfer_sub = transfer_class.objects.get(id=transfer_id)
    template_name = "%s.html" % trans.transfer_type.lower()
    return render_to_response(template_name, {'transfer':transfer_sub},
            context_instance=RequestContext(request))    

def project(request, project_id):
    if request.method == 'POST':
        return HttpResponseNotAllowed()
    try:
        project = models.Project.objects.get(id=project_id)
    except models.Project.DoesNotExist:
        raise Http404
    return render_to_response("project.html", {'project':project},
        context_instance=RequestContext(request))

def transfer_received(request, transfer_id):
    if request.method == 'GET':
        return HttpResponseNotAllowed()
    if not request.user.is_authenticated() or not request.user.is_staff:
        return HttpResponseForbidden()
    try:
        transfer = models.Transfer.objects.get(id=transfer_id)
    except Transfer.DoesNotExist:
       raise Http404
    transfer.update_received(request.user)
    transfer.save()
    request.user.message_set.create(message="The transfer was marked as received.  A notification has been sent to %s." % 
            (transfer.user.email))

    return HttpResponseRedirect(reverse('transfer_url',
            args=[transfer_id]))

def create_transfer(request, transfer_type):
    if not request.user.is_authenticated():
        return HttpResponseForbidden()
    form_class = getattr(forms, transfer_type + "Form")
    template_name = "transfer_form.html"
    if request.method == 'GET':
        project_id = request.GET['project_id']         
    if request.method == 'POST':
        project_id = request.POST['project_id']
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            new_object = form.save(commit=False)                     
            new_object.project = models.Project.objects.get(id=project_id)
            new_object.user = models.User.objects.get(
                username=request.user.username)
            new_object.save()
            request.user.message_set.create(message="The transfer was registered.  A confirmation has been sent to %s and %s." % 
                    (new_object.user.email, new_object.project.contact_email))
            return HttpResponseRedirect(new_object.get_absolute_url())
    else:
        form = form_class()

    # Create the template, context, response
    return render_to_response(template_name, {'form':form,
            'project_id':project_id, 'transfer_type':transfer_type},
            context_instance=RequestContext(request))

@login_required
def transfer_list(request):
    """
    List all the relevant transfer info for a user or project or both.
    If any of the following conditions are not met, set a useful message 
    and send the user back to their page (where that message should 
    display).

    1. Any request must at least specify a username or a project id,
    or it is invalid.

    2. To see a particular project's info, a user must be at least 
    one of:

        a) explicitly associated with a project
        b) a superuser
        c) a staff member

    3. Only staff or superusers may see another user's projects.
    """
    q = TransferQuery(request=request)

    # Verify condition 1.  This must be true, kick them up if not.
    if not q.username and not q.project_id:
        request.user.message_set.create(message='Bad listing request.')
        return HttpResponseRedirect(reverse('overview_url', 
            args=[request.user.username]))

    # Verify condition 2.  Kick them up if not, also.
    if q.project_id:
        allow = False
        project = get_object_or_404(models.Project, id=q.project_id)
        # 2b and 2c.
        if request.user.is_superuser or request.user.is_staff:
            allow = True
        else:
            # 2a.
            if request.user in project.users.all():
                allow = True
        if not allow:
            request.user.message_set.create(message='Invalid transfer project')
            return HttpResponseRedirect(reverse('overview_url', 
                args=[request.user.username]))

    # Verify condition 3.
    if q.username and request.user.username != q.username:
        if not (request.user.is_staff or request.user.is_superuser):
            request.user.message_set.create(message='Invalid transfer user')
            return HttpResponseRedirect(reverse('overview_url', 
                args=[request.user.username]))

    # If they've made it this far, it's a valid request.
    transfers = q.query()
    return render_to_response('transfer_list.html', 
        {'query': q, 'transfers': transfers}, 
        context_instance=RequestContext(request))

