# 🧭 Developer Onboarding Checklist

Welcome to the project! Follow this checklist to get up and running fast.

---

## ✅ 1. Setup

- [ ] Clone the repo: `git clone <repo-url>`
- [ ] Install Python dependencies: `pip install -r requirements.txt`
- [ ] Install Playwright browsers: `playwright install`
- [ ] Set up `.env` or required environment variables (`LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD`, etc.)

---

## ⚙️ 2. Automation Workflow

- [ ] Read `docs/automation-prompt-template.md`
- [ ] Use a Cursor AI prompt for every change
- [ ] Example prompt:
```cursor
// Add a debug log after LinkedIn login
logger.info("✅ Logged into LinkedIn successfully.");
```

---

## 🧪 3. Testing

- [ ] Run script with `python main.py --config config.json`
- [ ] Check logs in `logs/app.log`
- [ ] Verify output in `data/output/`

---

## 📝 4. Contribution

- [ ] Use `.github/ISSUE_TEMPLATE/feature_request.md` for new features
- [ ] Include an automation prompt in every issue or PR
- [ ] Follow logging and code style conventions

---

## 🚀 You're Ready!

Happy building. If stuck, check:
- README.md for quickstart
- CONTRIBUTING.md for collaboration guidelines
- Ask for help in the team Slack! 