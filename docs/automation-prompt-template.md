# 🎯 Cursor AI Automation Prompt Template

Use this template for every update, bug fix, or feature to ensure consistent and automated development.

## Format

```cursor
// Describe the change clearly in one sentence
// Explain where the change should be made and how
<your code or instructions>
```

## Examples

### Example 1: Adding Debug Logging
```cursor
// Add a debug log after the login redirect to confirm successful authentication
Add this line after page.goto():
logger.info("✅ Successfully navigated to LinkedIn login page.");
```

### Example 2: Browser Initialization
```cursor
// Add a check to ensure browser is initialized before calling goto
Insert before page.goto():
if self.browser is None:
    playwright = await async_playwright().start()
    self.browser = await playwright.chromium.launch(headless=True)
```

### Example 3: Error Handling
```cursor
// Add error handling for LinkedIn login failures
Add try-catch block around login logic:
try:
    await self.page.goto('https://www.linkedin.com/login')
except Exception as e:
    logger.error(f"Login failed: {e}")
    await self.page.screenshot(path='login_error.png')
    raise
```

## Guidelines

1. **Be Specific**
   - Clearly state what file to modify
   - Specify exact line numbers or locations
   - Include all necessary imports

2. **Include Context**
   - Explain why the change is needed
   - Describe the expected outcome
   - List any dependencies or prerequisites

3. **Success Criteria**
   - Define how to verify the change worked
   - Include test cases if applicable
   - Specify expected output or behavior

4. **Error Handling**
   - Include error cases to consider
   - Specify how to handle failures
   - Add logging or debugging steps

## Best Practices

1. **Keep it Simple**
   - One change per prompt
   - Clear, concise instructions
   - Minimal manual steps

2. **Test First**
   - Verify the automation works
   - Document any manual steps
   - Include rollback instructions

3. **Document Everything**
   - Explain the purpose
   - List prerequisites
   - Include examples

## Template

```markdown
💡 Goal: [Clear description of the change]

🎯 Tasks (automate in sequence):
1. [Step 1]
2. [Step 2]
3. [Step 3]

✅ Success Criteria:
- [ ] [Criterion 1]
- [ ] [Criterion 2]

🔍 Verification Steps:
1. [How to verify]
2. [Expected output]

⚠️ Error Handling:
- [Error case 1]
- [Error case 2]
``` 