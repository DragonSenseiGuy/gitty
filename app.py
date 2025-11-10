from flask import Flask, render_template, request, redirect, url_for, flash, session
import subprocess
import os
import logging
import re
from dotenv import load_dotenv

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("git_client.log"),
        logging.StreamHandler() # Also log to console
    ]
)

load_dotenv()
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY # Replace with a strong, random key in production

def run_git_command(command, cwd):
    """Helper function to run a git command and return its output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Git command failed in {cwd}: {command}\nError: {e.stderr}")
        flash(f"Git command failed: {e.stderr}", "danger")
        return None
    except FileNotFoundError:
        logging.error(f"Git command not found. Is git installed and in your PATH?")
        flash(f"Git command not found. Is git installed and in your PATH?", "danger")
        return None

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/home")
def home():
    return render_template("index.html")

@app.route("/clone", methods=["POST"])
def clone_repo():
    repo_url = request.form.get("repo_url")
    destination_path = request.form.get("destination_path")

    if not repo_url or not destination_path:
        flash("Missing repository URL or destination path.", "danger")
        return redirect(url_for("home"))

    if not os.path.isabs(destination_path):
        flash("Destination path must be absolute.", "danger")
        return redirect(url_for("home"))

    logging.info(f"Attempting to clone repository from {repo_url} to {destination_path}")
    
    # We don't use the helper here because we want to clone *into* the directory, not from it.
    try:
        parent_dir = os.path.dirname(destination_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            
        subprocess.run(
            ["git", "clone", repo_url, destination_path],
            capture_output=True, text=True, check=True
        )
        logging.info(f"Successfully cloned repository from {repo_url} to {destination_path}")
        flash(f"Repository cloned successfully to {destination_path}", "success")
        session['repo_path'] = destination_path
        return redirect(url_for('repo_view'))
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to clone repository from {repo_url}. Error: {e.stderr}")
        flash(f"Failed to clone repository: {e.stderr}", "danger")
    except Exception as e:
        logging.error(f"An unexpected error occurred during clone: {str(e)}")
        flash(f"An unexpected error occurred: {str(e)}", "danger")
    
    return redirect(url_for("home"))

@app.route("/open_local", methods=["POST"])
def open_local_repo():
    local_repo_path = request.form.get("local_repo_path")

    if not local_repo_path:
        flash("Missing local repository path.", "danger")
        return redirect(url_for("home"))

    if not os.path.isabs(local_repo_path) or not os.path.isdir(local_repo_path):
        flash("Path must be an absolute path to a valid directory.", "danger")
        return redirect(url_for("home"))
        
    # Check if it's a git repository
    if not os.path.isdir(os.path.join(local_repo_path, '.git')):
        flash("The provided path is not a valid Git repository.", "danger")
        return redirect(url_for("home"))

    logging.info(f"Successfully opened local repository: {local_repo_path}")
    session['repo_path'] = local_repo_path
    return redirect(url_for('repo_view'))

@app.route("/repo")
def repo_view():
    repo_path = session.get('repo_path')
    if not repo_path:
        flash("No repository selected.", "info")
        return redirect(url_for('home'))

    repo_name = os.path.basename(repo_path)

    # Get status
    status_output = run_git_command(["git", "status", "--porcelain"], cwd=repo_path)
    unstaged_files = []
    untracked_files = []
    if status_output:
        for line in status_output.splitlines():
            if line.startswith('??'):
                untracked_files.append(line[3:])
            else:
                unstaged_files.append(line[3:])

    # Get remotes
    remote_output = run_git_command(["git", "remote", "-v"], cwd=repo_path)
    remotes = remote_output.splitlines() if remote_output else []
    remote_names = list(set([line.split()[0] for line in remotes]))

    return render_template(
        "commands.html",
        repo_path=repo_path,
        repo_name=repo_name, # Pass the folder name to the template
        unstaged_files=unstaged_files,
        untracked_files=untracked_files,
        remotes=remotes,
        remote_names=remote_names
    )

@app.route("/commit", methods=["POST"])
def commit():
    repo_path = session.get('repo_path')
    if not repo_path:
        return redirect(url_for('home'))
        
    commit_message = request.form.get("commit_message")
    if not commit_message:
        flash("Commit message cannot be empty.", "danger")
        return redirect(url_for('repo_view'))

    # Stage all files
    run_git_command(["git", "add", "."], cwd=repo_path)
    
    # Commit
    commit_output = run_git_command(["git", "commit", "-m", commit_message], cwd=repo_path)
    
    if commit_output is not None:
        flash(f"Successfully committed.", "success")
        logging.info(f"New commit in {repo_path}: {commit_message}")

    return redirect(url_for('repo_view'))

@app.route("/add_remote", methods=["POST"])
def add_remote():
    repo_path = session.get('repo_path')
    if not repo_path:
        return redirect(url_for('home'))

    remote_name = request.form.get("remote_name")
    remote_url = request.form.get("remote_url")

    if not remote_name or not remote_url:
        flash("Remote name and URL are required.", "danger")
        return redirect(url_for('repo_view'))

    remote_output = run_git_command(["git", "remote", "add", remote_name, remote_url], cwd=repo_path)

    if remote_output is not None:
        flash(f"Successfully added remote '{remote_name}'.", "success")
        logging.info(f"Added remote {remote_name} ({remote_url}) to {repo_path}")

    return redirect(url_for('repo_view'))

@app.route("/push", methods=["POST"])
def push():
    repo_path = session.get('repo_path')
    if not repo_path:
        return redirect(url_for('home'))

    remote_name = request.form.get("remote_name")
    branch_name = request.form.get("branch_name")

    if not remote_name or not branch_name:
        flash("Remote and branch name are required.", "danger")
        return redirect(url_for('repo_view'))

    push_output = run_git_command(["git", "push", remote_name, branch_name], cwd=repo_path)

    if push_output is not None:
        flash(f"Successfully pushed to {remote_name}/{branch_name}.", "success")
        logging.info(f"Pushed to {remote_name}/{branch_name} from {repo_path}")

    return redirect(url_for('repo_view'))