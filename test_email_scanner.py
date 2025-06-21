import pytest
from email_scanner import EmailScanner

@pytest.mark.parametrize("parser, email_body, expected_apply_url", [
    # LinkedIn: direct apply link present
    (
        '_parse_linkedin_job_alert',
        '''Software Engineer at TestCorp\nRemote\nhttps://www.linkedin.com/jobs/view/1234567890\nhttps://www.linkedin.com/jobs/apply/1234567890''',
        'https://www.linkedin.com/jobs/apply/1234567890'
    ),
    # LinkedIn: no direct apply link, fallback to job_url
    (
        '_parse_linkedin_job_alert',
        '''Software Engineer at TestCorp\nRemote\nhttps://www.linkedin.com/jobs/view/1234567890''',
        'https://www.linkedin.com/jobs/view/1234567890'
    ),
    # Indeed: direct apply link present
    (
        '_parse_indeed_job_alert',
        '''Data Scientist\nDataInc\nRemote\nhttps://ca.indeed.com/viewjob?jk=abcdef123456\nhttps://ca.indeed.com/applystart/abcdef123456''',
        'https://ca.indeed.com/applystart/abcdef123456'
    ),
    # Indeed: no direct apply link, fallback to job_url
    (
        '_parse_indeed_job_alert',
        '''Data Scientist\nDataInc\nRemote\nhttps://ca.indeed.com/viewjob?jk=abcdef123456''',
        'https://ca.indeed.com/viewjob?jk=abcdef123456'
    ),
    # Glassdoor: direct apply link present
    (
        '_parse_glassdoor_job_alert',
        '''Product Manager\nGlassInc\nRemote\nhttps://www.glassdoor.com/job-listing/12345\nhttps://www.glassdoor.com/partner/jobListing/applyJobListing.htm?jobListingId=12345''',
        'https://www.glassdoor.com/partner/jobListing/applyJobListing.htm?jobListingId=12345'
    ),
    # Glassdoor: no direct apply link, fallback to job_url
    (
        '_parse_glassdoor_job_alert',
        '''Product Manager\nGlassInc\nRemote\nhttps://www.glassdoor.com/job-listing/12345''',
        'https://www.glassdoor.com/job-listing/12345'
    ),
    # Generic: two links, second is apply_url
    (
        '_parse_generic_job_alert',
        '''AI Engineer\nGenCorp\nRemote\nhttps://generic.com/job/123\nhttps://generic.com/apply/123''',
        'https://generic.com/apply/123'
    ),
    # Generic: only one link, fallback to job_url
    (
        '_parse_generic_job_alert',
        '''AI Engineer\nGenCorp\nRemote\nhttps://generic.com/job/123''',
        'https://generic.com/job/123'
    ),
])
def test_apply_url_extraction(parser, email_body, expected_apply_url):
    scanner = EmailScanner()
    parse_func = getattr(scanner, parser)
    jobs = parse_func(email_body)
    assert len(jobs) > 0
    for job in jobs:
        assert 'apply_url' in job
        assert job['apply_url'] == expected_apply_url 