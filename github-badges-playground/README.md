# GitHub Badges Playground

This tiny scaffold helps you earn several easy GitHub profile badges by running automated actions in a new repository.

Workflows included:
- `.github/workflows/quickdraw.yml` — creates and closes an issue (Quickdraw)
- `.github/workflows/yolo_pullshark.yml` — creates a tiny branch, opens a PR, and merges it (YOLO / Pull Shark)
- `.github/workflows/heart.yml` — creates an issue, reacts with a ❤️, and closes it (Heart On Your Sleeve)

How to use
1. Create a new **public** repository on GitHub (name it `github-badges-playground` or whatever you like).
2. Push this folder to the new repository as `main`/`master`.
3. In the repository, open the **Actions** tab and allow workflows to run (they will run automatically on push; you can also trigger them manually via "Run workflow").
4. Run the workflows (or wait for them) — they will create/close issues and PRs quickly, satisfying the badge actions.

Quick push commands
```bash
git init
git add .
git commit -m "Add GitHub badges playground"
git branch -M main
git remote add origin git@github.com:<your-username>/<repo>.git
git push -u origin main
```

Notes
- Workflows use the provided `GITHUB_TOKEN`. Make the repo public and allow Actions to run. If your account uses branch protection rules, the auto-merge step might be blocked.
- Badges are awarded by GitHub and may take a few minutes to appear on your profile.

Enjoy — tell me when you've pushed and I'll suggest the best workflow to run first.
