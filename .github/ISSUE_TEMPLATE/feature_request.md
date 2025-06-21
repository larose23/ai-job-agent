---
name: Feature request
about: Suggest a new feature or improvement
title: "[Feature] <your title here>"
labels: enhancement
assignees: ''

---

## Summary  
<!-- Describe the feature you're requesting -->

## Why is this needed?  
<!-- Describe the problem or opportunity -->

## Solution  
<!-- Describe your proposed solution -->

## Automation Prompt  
<!-- Include the Cursor AI automation prompt that can apply the change -->

Example:
```cursor
// Add a debug log after the login redirect to confirm successful authentication
Add this line after page.goto():
logger.info("✅ Successfully navigated to LinkedIn login page.");
```

## Checklist
- [ ] I have included a clear automation prompt
- [ ] I have tested the automation steps
- [ ] I have documented any manual steps required
- [ ] I have included success criteria 