---
allowed-tools: ["Bash(*)", "Read", "Write"]
description: "Commit changes, create project archive, and generate completion report"
---

# Review Preparation Command

I'll commit your changes, create a project archive excluding large files, and generate a comprehensive completion report.

This will:
1. **Commit and push** any pending changes with a structured commit message
2. **Create project archive** excluding `*.mp3`, `*.wav`, `*.zip`, and `.git/` directories  
3. **Generate completion report** with implementation details, database metrics, and next steps
4. **Provide review summary** with all deliverables ready

## Executing Review Preparation

!scripts/review_prep.sh $ARGUMENTS

The review preparation is now complete! Check the generated files:
- `REVIEW_REPORT_*.md` - Detailed completion report
- `podcast-scraper-review-*.zip` - Complete project archive

Your changes have been committed and pushed, and all review materials are ready.