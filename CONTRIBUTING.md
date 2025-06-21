# Contributing to AI Job Agent

Thank you for your interest in contributing to AI Job Agent! This document provides guidelines and instructions for contributing to the project.

## Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test your changes
5. Submit a pull request

## Code Style

- Follow PEP 8 guidelines
- Use type hints
- Write docstrings for all functions and classes
- Keep functions small and focused
- Use meaningful variable names

## Testing

- Write tests for new features
- Ensure all tests pass before submitting
- Include both unit and integration tests
- Test edge cases and error conditions

## Documentation

- Update README.md if needed
- Document new features
- Include examples for complex features
- Keep documentation up to date

## Automation Policy

### Overview

Every code change, improvement, or bug fix must include a Cursor AI automation prompt. This ensures consistent and fast development, especially for infrastructure and repetitive updates.

### Requirements

1. **Include Automation Prompt**
   - Every task must have a Cursor AI automation prompt
   - The prompt should be clear and actionable
   - Include all necessary steps and success criteria

2. **Prompt Format**
   ```markdown
   💡 Goal: [Clear description of the change]

   🎯 Tasks (automate in sequence):
   1. [Step 1]
   2. [Step 2]
   3. [Step 3]

   ✅ Success Criteria:
   - [ ] [Criterion 1]
   - [ ] [Criterion 2]
   ```

3. **Testing Automation**
   - Test the automation before submitting changes
   - Verify all steps can be automated
   - Document any manual steps that cannot be automated

4. **Documentation**
   - Include the automation prompt in your pull request
   - Document any manual steps required
   - Explain any assumptions or prerequisites

### Example

Here's an example of a good automation prompt:

```markdown
💡 Goal: Add error handling for LinkedIn login failures

🎯 Tasks (automate in sequence):
1. Open `linkedin_scraper.py`
2. Add try-catch block around login logic
3. Add error logging and screenshots
4. Update tests to cover error cases

✅ Success Criteria:
- [ ] Login errors are caught and logged
- [ ] Screenshots are saved for debugging
- [ ] Tests pass with error cases
```

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the documentation with any new features
3. Include the automation prompt in your PR description
4. Ensure all tests pass
5. Wait for review and address any feedback

## Questions?

If you have any questions, please open an issue or contact the maintainers. 