import os
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, render_template_string

app = Flask(__name__)

# Maximum upload size: 10 MB
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
DEOBF = BASE_DIR / "Deobfuscator" / "deobf" / "bin" / "deob.py"

PAGE = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>Lua Deobfuscator</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 700px;
            margin: 60px auto;
            padding: 20px;
        }
        input, button {
            padding: 10px;
            margin-top: 12px;
        }
        .error {
            color: #b00020;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <h1>Lua Deobfuscator</h1>

    {% if error %}
        <p class="error">{{ error }}</p>
    {% endif %}

    <form method="post" enctype="multipart/form-data">
        <input type="file" name="file" accept=".lua,.luau,.txt" required>
          

        <button type="submit">Deobfuscate</button>
    </form>
</body>
</html>
"""


@app.get("/")
def home():
    return render_template_string(PAGE)


@app.post("/")
def deobfuscate():
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        return render_template_string(PAGE, error="Please select a Lua file.")

    original_name = Path(uploaded.filename).name
    extension = Path(original_name).suffix.lower()

    if extension not in {".lua", ".luau", ".txt"}:
        return render_template_string(
            PAGE,
            error="Only .lua, .luau, and .txt files are supported.",
        )

    with tempfile.TemporaryDirectory(prefix="deobfuscator_") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / original_name
        output_path = temp_path / "deobfuscated.lua"

        uploaded.save(input_path)

        command = [
            "python3",
            str(DEOBF),
            str(input_path),
            "--no-pypy",
            "--no-devirt",
            "--no-fold",
            "--no-tidy",
            "-o",
            str(output_path),
        ]

        try:
            result = subprocess.run(
                command,
                cwd=str(DEOBF.parent),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired:
            return render_template_string(
                PAGE,
                error="The file took too long to process.",
            )
        except Exception as exc:
            return render_template_string(
                PAGE,
                error=f"Could not start the deobfuscator:\n{exc}",
            )

        if result.returncode != 0 or not output_path.exists():
            details = (result.stderr or result.stdout or "Unknown error").strip()
            return render_template_string(
                PAGE,
                error=f"Deobfuscation failed:\n{details}",
            )

        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"{Path(original_name).stem}_deobfuscated.lua",
            mimetype="text/plain",
        )


@app.errorhandler(413)
def file_too_large(_error):
    return render_template_string(
        PAGE,
        error="The uploaded file is too large. Maximum size is 10 MB.",
    ), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
