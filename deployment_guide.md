# Deploying to Hugging Face Spaces (Option A)

Hugging Face Spaces is the best free option for FocusFlow because it supports Docker, allowing us to compile the C++ module in the cloud.

## Step 1: Create the Space
1. Go to [Hugging Face Spaces](https://huggingface.co/spaces).
2. Click **"Create new Space"**.
3. Name your space (e.g., `FocusFlow`).
4. Select **Docker** as the SDK.
5. Choose **"Blank"** template.
6. Set visibility to **Public** or **Private**.
7. Click **Create Space**.

## Step 2: Push your code
Since your code is already on GitHub, you can either:

### Method A: Connect GitHub (Easiest)
1. On your new Space page, go to **Settings**.
2. Find the **"Connected GitHub Repository"** section.
3. Link your `kush-rc/FocusFlow` repository.
4. Hugging Face will automatically build and deploy whenever you push to GitHub.

### Method B: Manually Push via Git
1. Get the Git URL of your Space (ends in `.git`).
2. Add it as a new remote:
   ```bash
   git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/FocusFlow
   ```
3. Push to Hugging Face:
   ```bash
   git push -f hf main
   ```

## Step 3: Monitoring the Build
- Once pushed, go to the **"Logs"** tab in your Space.
- You will see the Docker image building and the C++ module compiling.
- Once finished, the Status will change to **"Running"**.

## Important Notes
- **Port**: Hugging Face requires the app to listen on port `7860`. The `Dockerfile` and `main.py` are already configured for this.
- **Webcam**: Ensure your site is accessed via `https` (Hugging Face provides this automatically) so the browser allows camera access.
