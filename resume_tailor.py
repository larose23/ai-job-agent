"""
Resume tailoring and cover letter generation module for the AI Job Agent application.
Uses OpenAI GPT-4 to tailor resumes and generate personalized cover letters.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional, Any, List, Union

from openai import OpenAI
from dotenv import load_dotenv

from helpers import load_config, sanitize_filename, create_directory_if_not_exists
from logger import logger, notify_slack

load_dotenv()

class ResumeTailor:
    """AI-powered resume tailoring and cover letter generation."""
    
    def __init__(self, config_path: str = "config.json") -> None:
        """
        Initialize the resume tailor with configuration.
        
        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.logger = logger
        
        # Initialize OpenAI client
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        if not api_key:
            error_msg = "OpenAI API key not found in environment variables"
            logger.error(error_msg)
            notify_slack(error_msg)
            raise ValueError(error_msg)
            
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info(f"Resume tailor initialized with OpenAI API at {base_url}")
        
        # Load base resume
        self.base_resume = self._load_base_resume()
        
        # Ensure output directories exist
        create_directory_if_not_exists("data/cover_letters")
    
    def _load_base_resume(self) -> str:
        """
        Load the base resume from file.
        
        Returns:
            Base resume text
            
        Raises:
            FileNotFoundError: If base resume file doesn't exist
        """
        resume_path = "data/base_resume.txt"
        
        try:
            with open(resume_path, 'r', encoding='utf-8') as f:
                resume_text = f.read().strip()
            
            if not resume_text:
                raise ValueError("Base resume file is empty")
            
            self.logger.info("Successfully loaded base resume")
            return resume_text
            
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Base resume file not found at {resume_path}. "
                "Please create this file with your resume content."
            )
        except Exception as e:
            self.logger.error(f"Error loading base resume: {e}")
            raise
    
    def tailor_resume_and_cover(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tailor resume and generate cover letter for a specific job.
        
        Args:
            job: Job dictionary with title, company, location, salary_text, full_description
            
        Returns:
            Dictionary with file paths and recruiter email
        """
        self.logger.info(f"Tailoring resume for {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
        
        # Create the prompt for GPT-4
        prompt = self._create_tailoring_prompt(job)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert resume writer and career coach. You help job seekers tailor their resumes and write compelling cover letters for specific job opportunities."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            # Parse the response
            response_text = response.choices[0].message.content.strip()
            ai_output = self._parse_ai_response(response_text)
            
            # Save the outputs to files
            file_paths = self._save_tailored_content(job, ai_output)
            
            return {
                'delta_resume_file': file_paths['delta_resume'],
                'cover_letter_file': file_paths['cover_letter'],
                'recruiter_email': ai_output.get('recruiter_email'),
                'ai_response': ai_output
            }
            
        except Exception as e:
            self.logger.error(f"Error in AI tailoring: {e}")
            raise
    
    def _create_tailoring_prompt(self, job: Dict[str, Any]) -> str:
        """
        Create the prompt for GPT-4 to tailor resume and generate cover letter.
        
        Args:
            job: Job dictionary
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""
Base Resume:
{self.base_resume}

Job Title: {job.get('title', 'Not specified')}
Company: {job.get('company', 'Not specified')}
Location: {job.get('location', 'Not specified')}
Salary: {job.get('salary_text', 'Not specified')}
Job Description: {job.get('full_description', 'Not specified')}

Instructions:
1. Provide a list of specific bullet-point edits ("Delta Resume") to transform the Base Resume to optimally match this job. Emphasize required skills, responsibilities, and keywords from the job description. Focus on:
   - Adding relevant keywords from the job description
   - Highlighting matching experience and skills
   - Quantifying achievements that align with job requirements
   - Reordering or emphasizing relevant sections

2. Generate a 200-word personalized cover letter that:
   - References 3 main requirements from the job description
   - Shows how the applicant's experience addresses these requirements
   - Demonstrates knowledge of the company
   - Expresses genuine interest in the role
   - Has a professional yet engaging tone

3. If possible, extract or guess a recruiter or hiring manager's email domain from the company name and suggest probable email patterns (e.g., first.last@company.com, firstname.lastname@company.com).

Return output as a JSON object with this exact structure:
{{
  "delta_resume": "• [Specific edit 1]\\n• [Specific edit 2]\\n• [Specific edit 3]\\n...",
  "cover_letter": "[Full cover letter text]",
  "recruiter_email": "[email@company.com or null if cannot determine]"
}}

Ensure the JSON is valid and properly escaped.
"""
        return prompt
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the AI response and extract structured data.
        
        Args:
            response_text: Raw response from OpenAI
            
        Returns:
            Parsed response dictionary
        """
        try:
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                parsed_response = json.loads(json_text)
                
                # Validate required fields
                required_fields = ['delta_resume', 'cover_letter']
                for field in required_fields:
                    if field not in parsed_response:
                        raise ValueError(f"Missing required field: {field}")
                
                return parsed_response
            else:
                raise ValueError("No valid JSON found in response")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {e}")
            # Fallback: try to extract content manually
            return self._manual_parse_response(response_text)
        except Exception as e:
            self.logger.error(f"Error parsing AI response: {e}")
            raise
    
    def _manual_parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Manually parse AI response if JSON parsing fails.
        
        Args:
            response_text: Raw response text
            
        Returns:
            Parsed response dictionary
        """
        # Try to extract delta resume
        delta_resume = ""
        cover_letter = ""
        recruiter_email = None
        
        lines = response_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if 'delta' in line.lower() and 'resume' in line.lower():
                current_section = 'delta_resume'
                continue
            elif 'cover' in line.lower() and 'letter' in line.lower():
                current_section = 'cover_letter'
                continue
            elif 'email' in line.lower() and '@' in line:
                # Extract email
                email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', line)
                if email_match:
                    recruiter_email = email_match.group(0)
                continue
            
            if current_section == 'delta_resume':
                if line.startswith('•') or line.startswith('-'):
                    delta_resume += line + '\n'
            elif current_section == 'cover_letter':
                cover_letter += line + '\n'
        
        return {
            'delta_resume': delta_resume.strip(),
            'cover_letter': cover_letter.strip(),
            'recruiter_email': recruiter_email
        }
    
    def _save_tailored_content(self, job: Dict[str, Any], ai_output: Dict[str, Any]) -> Dict[str, str]:
        """
        Save tailored resume and cover letter to files.
        
        Args:
            job: Job dictionary
            ai_output: AI response dictionary
            
        Returns:
            Dictionary with file paths
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        company = sanitize_filename(job.get('company', 'unknown'))
        title = sanitize_filename(job.get('title', 'unknown'))
        
        # Save delta resume
        delta_resume_path = f"data/delta_resumes/{company}_{title}_{timestamp}.txt"
        create_directory_if_not_exists("data/delta_resumes")
        with open(delta_resume_path, 'w', encoding='utf-8') as f:
            f.write(ai_output['delta_resume'])
        
        # Save cover letter
        cover_letter_path = f"data/cover_letters/{company}_{title}_{timestamp}.txt"
        with open(cover_letter_path, 'w', encoding='utf-8') as f:
            f.write(ai_output['cover_letter'])
        
        self.logger.info(f"Saved tailored content for {company} - {title}")
        
        return {
            'delta_resume': delta_resume_path,
            'cover_letter': cover_letter_path
        }
    
    def generate_recruiter_email_suggestions(self, company: str) -> List[str]:
        """
        Generate possible recruiter email patterns for a company.
        
        Args:
            company: Company name
            
        Returns:
            List of possible email patterns
        """
        # Extract domain from company name
        domain = company.lower().replace(' ', '').replace('.', '') + '.com'
        
        # Common email patterns
        patterns = [
            f"recruiting@{domain}",
            f"careers@{domain}",
            f"jobs@{domain}",
            f"hr@{domain}",
            f"talent@{domain}"
        ]
        
        return patterns
    
    def create_full_tailored_resume(self, job: Dict[str, Any], delta_resume: str) -> str:
        """
        Create a full tailored resume by applying delta changes.
        
        Args:
            job: Job dictionary
            delta_resume: Delta resume text
            
        Returns:
            Full tailored resume text
        """
        # Split base resume into sections
        sections = self.base_resume.split('\n\n')
        
        # Apply delta changes
        for line in delta_resume.split('\n'):
            if line.startswith('•') or line.startswith('-'):
                # Extract section and content
                parts = line[1:].strip().split(':')
                if len(parts) == 2:
                    section_name = parts[0].strip()
                    content = parts[1].strip()
                    
                    # Find and update section
                    for i, section in enumerate(sections):
                        if section_name.lower() in section.lower():
                            sections[i] = section + '\n' + content
                            break
        
        # Join sections back together
        return '\n\n'.join(sections)


def tailor_resume_and_cover(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tailor resume and generate cover letter for a job.
    
    Args:
        job: Job dictionary
        
    Returns:
        Dictionary with file paths and recruiter email
    """
    tailor = ResumeTailor()
    return tailor.tailor_resume_and_cover(job)


def batch_tailor_resumes(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Tailor resumes for multiple jobs.
    
    Args:
        jobs: List of job dictionaries
        
    Returns:
        List of dictionaries with file paths and recruiter emails
    """
    tailor = ResumeTailor()
    results = []
    
    for job in jobs:
        try:
            result = tailor.tailor_resume_and_cover(job)
            results.append(result)
        except Exception as e:
            logger.error(f"Error tailoring resume for {job.get('title', 'Unknown')}: {e}")
            continue
    
    return results


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Load test job data
        with open('data/test_job.json', 'r') as f:
            test_job = json.load(f)
        
        # Test resume tailoring
        result = tailor_resume_and_cover(test_job)
        logger.info(f"Successfully tailored resume for {test_job['title']}")
        logger.info(f"Files saved: {result['delta_resume_file']}, {result['cover_letter_file']}")
        
    except Exception as e:
        logger.error(f"Error in resume tailoring: {e}")
        sys.exit(1)

