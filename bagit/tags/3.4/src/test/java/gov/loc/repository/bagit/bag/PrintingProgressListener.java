package gov.loc.repository.bagit.bag;

import java.text.MessageFormat;

import gov.loc.repository.bagit.ProgressListener;

public class PrintingProgressListener implements ProgressListener
{
	@Override
	public void reportProgress(String activity, Object item, Long count, Long total) 
	{
		System.out.println(MessageFormat.format("{0} {1} ({2} of {3})", activity, item, count, total));
	}
}
