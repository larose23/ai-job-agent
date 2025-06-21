import asyncio
import pytest
from job_application import JobApplication

# Mock job and user profile data
mock_job_linkedin = {
    'title': 'Software Engineer',
    'company': 'TestCorp',
    'location': 'Remote',
    'source': 'LinkedIn',
    'apply_url': 'https://www.linkedin.com/jobs/view/1234567890/'
}

mock_job_indeed = {
    'title': 'Data Scientist',
    'company': 'DataInc',
    'location': 'Remote',
    'source': 'Indeed',
    'apply_url': 'https://www.indeed.com/viewjob?jk=abcdef123456'
}

mock_user_profile = {
    'name': 'Test User',
    'email': 'testuser@example.com',
    'phone': '+1234567890',
    'resume_path': 'base_resume.txt'
}

@pytest.mark.asyncio
async def test_linkedin_application():
    async with JobApplication() as app:
        result = await app.apply_to_job(mock_job_linkedin, mock_user_profile)
        assert result is False  # Should fail gracefully (no real Easy Apply button)

@pytest.mark.asyncio
async def test_indeed_application():
    async with JobApplication() as app:
        result = await app.apply_to_job(mock_job_indeed, mock_user_profile)
        assert result is False  # Should fail gracefully (no real apply button)

if __name__ == "__main__":
    asyncio.run(test_linkedin_application())
    asyncio.run(test_indeed_application()) 