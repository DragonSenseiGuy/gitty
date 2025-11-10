from flask import Flask, render_template, request, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/clone", methods=["POST"])
def clone_repo():
    data = request.get_json()
    repo_url = data.get("url")
    destination_path = data.get("destination")

    if not repo_url or not destination_path:
        return jsonify({"status": "error", "message": "Missing repository URL or destination path."}), 400

    # Security check: ensure the destination is an absolute path and doesn't do anything tricky
    if not os.path.isabs(destination_path):
        return jsonify({"status": "error", "message": "Destination path must be absolute."}), 400

    try:
        # Ensure the parent directory of the destination exists
        parent_dir = os.path.dirname(destination_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            
        # Execute the git clone command
        result = subprocess.run(
            ["git", "clone", repo_url, destination_path],
            capture_output=True,
            text=True,
            check=True
        )
        return jsonify({"status": "success", "message": f"Repository cloned successfully to {destination_path}", "output": result.stdout})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": "Failed to clone repository.", "details": e.stderr}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500