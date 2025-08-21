import os
import re
from flask import Flask, request, render_template, jsonify
from PyPDF2 import PdfReader

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

RESUME_SECTIONS = {}  


def extract_text_from_pdf(path):
    """Extract all text from a PDF file (returns plain text)."""
    reader = PdfReader(path)
    text_parts = []
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            text_parts.append(txt)
    return "\n".join(text_parts).strip()


def split_into_sections(resume_text):
    
    sections = {"key": "", "skills": "", "experience": "", "project": "", "education": ""}
    current_section = None
    temp_intro = []

    lines = [ln.rstrip() for ln in resume_text.splitlines()]

    for line in lines:
        clean = line.strip()
        if not clean:
            continue

        if re.match(r'^(?:key|objective|summary|profile|about me|career objective|professional summary)\b[:\-]?', clean, re.I):
            current_section = "key"
            continue
        if re.match(r'^(?:skills?|technical skills|skills & abilities|skills and abilities)\b[:\-]?', clean, re.I):
            current_section = "skills"
            continue
        if re.match(r'^(?:education|academic|qualifications?|qualification|academic background)\b[:\-]?', clean, re.I):
            current_section = "education"
            continue
        if re.match(r'^(?:experience|work experience|employment|professional experience|career)\b[:\-]?', clean, re.I):
            current_section = "experience"
            continue
        if re.match(r'^(?:projects?|project work|personal projects|academic projects)\b[:\-]?', clean, re.I):
            current_section = "project"
            continue

        if clean.isupper() and len(clean.split()) <= 6:
            if re.search(r'EDUCATION', clean, re.I):
                current_section = "education"
                continue
            if re.search(r'EXPERIENCE', clean, re.I):
                current_section = "experience"
                continue
            if re.search(r'PROJECT', clean, re.I):
                current_section = "project"
                continue
            if re.search(r'SKILL|SKILLS', clean, re.I):
                current_section = "skills"
                continue
            if re.search(r'OBJECTIVE|SUMMARY|PROFILE', clean, re.I):
                current_section = "key"
                continue

        if current_section is None:
            temp_intro.append(clean)
        else:
            sections[current_section] += clean + " "

    if not sections["key"]:
        intro_lines = []
        for l in temp_intro:
            if re.search(r'(skills|education|experience|project|objective|summary|profile)', l, re.I):
                continue
            intro_lines.append(l)
            if len(intro_lines) >= 5:
                break
        sections["key"] = " ".join(intro_lines).strip()

    for k in sections:
        sections[k] = sections[k].strip()

    if not sections["project"] and sections["experience"]:
        project_candidates = []

        bullets = re.split(r'[\n•\-\u2022]+', sections["experience"])
        sentences = re.split(r'(?<=[\.\?!])\s+', sections["experience"])

        proj_keywords = r'(project|develop|designed?|build|built|deploy|deployed|implement|implemented|ml|ai|model|nlp|random forest|classification|regression|pipeline|architecture|integration)'

        for b in bullets:
            if re.search(proj_keywords, b, re.I):
                cleaned = b.strip()
                if cleaned:
                    project_candidates.append(cleaned)

        if not project_candidates:
            for s in sentences:
                if re.search(proj_keywords, s, re.I):
                    cleaned = s.strip()
                    if cleaned:
                        project_candidates.append(cleaned)

        if project_candidates:
            sections["project"] = " • ".join(project_candidates)

    return sections


def format_skills(skills_text):
    """Return HTML formatted skills as a list (attempts to identify sub-categories)."""
    if not skills_text:
        return ""

    s = skills_text.strip()

    markers = [
        "Programming Languages", "Programming Language",
        "Frameworks & Libraries", "Frameworks", "Libraries",
        "Tools", "Tools & IDEs", "Tools & IDE", "Tools & IDEs",
        "Database", "Databases", "Databases:"
    ]
    for mk in markers:
        s = re.sub(r'(?i)\b' + re.escape(mk) + r'\b', f'\n{mk}:', s)

    s = re.sub(r'\.\s+', '.\n', s)

    s = re.sub(r'\s+', ' ', s)

    lines = [ln.strip(" .:-") for ln in s.splitlines() if ln.strip()]
    items = []
    for ln in lines:
        if ':' in ln:
            header, rest = ln.split(':', 1)
            header = header.strip()
            rest = rest.strip()
            if rest:
                items.append(f"<strong>{header}:</strong> {rest}")
            else:
                items.append(f"<strong>{header}</strong>")
        else:
            items.append(ln)

    if not items:
        parts = [p.strip() for p in re.split(r',|\n', skills_text) if p.strip()]
        return "<ul>" + "".join(f"<li>{p}</li>" for p in parts) + "</ul>"

    return "<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>"


def format_projects(project_text):
    """Format project text into an HTML list."""
    if not project_text:
        return ""

    if '•' in project_text:
        parts = [p.strip() for p in project_text.split('•') if p.strip()]
    else:
        parts = [p.strip() for p in re.split(r'[\n\-–]+', project_text) if p.strip()]
        if len(parts) == 1:
            parts = [p.strip() for p in re.split(r'(?<=[\.\?!])\s+', project_text) if p.strip()]

    return "<ul>" + "".join(f"<li>{p}</li>" for p in parts) + "</ul>"


def format_experience(exp_text):
    """Format experience text into paragraphs/lists."""
    if not exp_text:
        return ""
    bullets = [b.strip() for b in re.split(r'[\n•\-\u2022]+', exp_text) if b.strip()]
    if len(bullets) > 1:
        return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
    sentences = [s.strip() for s in re.split(r'(?<=[\.\?!])\s+', exp_text) if s.strip()]
    if sentences:
        return "<p>" + " ".join(sentences) + "</p>"
    return "<p>" + exp_text + "</p>"


def answer_question(question):
    """Return answer based on resume sections"""
    q = question.lower()

    if "yourself" in q or "introduce" in q or "about you" in q or "key" in q or "objective" in q or "summary" in q or "profile" in q:
        return RESUME_SECTIONS.get("key") or "Key/Objective section not found."

    elif "skill" in q:
        return RESUME_SECTIONS.get("skills") or "Skills section not found."

    elif "experience" in q or "company" in q or "work" in q or "employment" in q:
        return RESUME_SECTIONS.get("experience") or "Work experience section not found."

    elif "project" in q:
        return RESUME_SECTIONS.get("project") or "Projects section not found."

    elif "education" in q or "academic" in q or "qualification" in q:
        return RESUME_SECTIONS.get("education") or "Education section not found."

    else:
        return "No matching section found in resume."


@app.route("/", methods=["GET", "POST"])
def index():
    global RESUME_SECTIONS
    if request.method == "POST":
        if "resume" not in request.files:
            return "No file uploaded", 400
        file = request.files["resume"]
        if file.filename == "":
            return "No selected file", 400

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        resume_text = extract_text_from_pdf(filepath)
        RESUME_SECTIONS = split_into_sections(resume_text)


        return render_template("index.html", uploaded=True)

    return render_template("index.html", uploaded=False)


@app.route("/ask", methods=["POST"])
def ask():
    if not RESUME_SECTIONS:
        return jsonify({"error": "No resume uploaded yet"})

    question = request.json.get("question", "")
    answer = answer_question(question)
    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=False, port=4500)
