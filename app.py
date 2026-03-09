from flask import Flask, render_template, request, redirect
import mysql.connector
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"

# Create uploads folder if not exists
if not os.path.exists("uploads"):
    os.makedirs("uploads")

# ================= SKILL MASTER LIST =================
SKILLS_LIST = [
    "python", "flask", "django",
    "html", "html5",
    "css", "css3",
    "javascript", "es6",
    "react", "react.js",
    "mysql", "sql",
    "git", "github",
    "bootstrap",
    "rest api", "responsive design",
    "dom manipulation"
]

# ================= DATABASE CONNECTION =================
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Swarali1805",
    database="ats_project"
)

cursor = db.cursor(dictionary=True)

# ================= AI FUNCTION =================
def calculate_similarity(job_desc, resume_text):
    if not resume_text.strip():
        return 0

    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([job_desc, resume_text])
    similarity = cosine_similarity(vectors[0], vectors[1])
    return float(similarity[0][0]) * 100

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cursor.fetchone()

        if user:
            return redirect("/dashboard")

    return render_template("login.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    # Fetch jobs
    cursor.execute("SELECT * FROM jobs")
    jobs = cursor.fetchall()

    # Analytics
    cursor.execute("SELECT COUNT(*) AS total_jobs FROM jobs")
    total_jobs = cursor.fetchone()["total_jobs"]

    cursor.execute("SELECT COUNT(*) AS total_candidates FROM resumes")
    total_candidates = cursor.fetchone()["total_candidates"]

    cursor.execute("SELECT COUNT(*) AS shortlisted FROM resumes WHERE status='Shortlisted'")
    shortlisted = cursor.fetchone()["shortlisted"]

    cursor.execute("SELECT COUNT(*) AS rejected FROM resumes WHERE status='Rejected'")
    rejected = cursor.fetchone()["rejected"]

    return render_template("dashboard.html",
                           jobs=jobs,
                           total_jobs=total_jobs,
                           total_candidates=total_candidates,
                           shortlisted=shortlisted,
                           rejected=rejected) 

# ================= ADD JOB =================
@app.route("/add-job", methods=["GET", "POST"])
def add_job():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        cursor.execute(
            "INSERT INTO jobs (title, description) VALUES (%s, %s)",
            (title, description)
        )
        db.commit()
        return redirect("/dashboard")

    return render_template("add_job.html")

# ================= UPLOAD RESUME =================
@app.route("/upload/<int:job_id>", methods=["GET", "POST"])
def upload_resume(job_id):
    if request.method == "POST":
        candidate_name = request.form["candidate_name"]
        file = request.files["resume"]

        if file.filename == "":
            return "No file selected"

        filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        # Extract resume text
        reader = PdfReader(filepath)
        resume_text = ""

        for page in reader.pages:
            text = page.extract_text()
            if text:
                resume_text += text

        resume_text_lower = resume_text.lower()

        # Get job description
        cursor.execute("SELECT description FROM jobs WHERE id=%s", (job_id,))
        job = cursor.fetchone()

        if not job:
            return "Job not found"

        job_desc = job["description"]
        job_desc_lower = job_desc.lower()

        # ================= SKILL EXTRACTION =================
        resume_skills = [skill for skill in SKILLS_LIST if skill in resume_text_lower]
        job_skills = [skill for skill in SKILLS_LIST if skill in job_desc_lower]

        matched_skills = list(set(resume_skills) & set(job_skills))
        missing_skills = list(set(job_skills) - set(resume_skills))

        matched_skills_str = ", ".join(matched_skills)
        missing_skills_str = ", ".join(missing_skills)

        # ================= AI SCORE =================
        score = calculate_similarity(job_desc, resume_text)

        # ================= STATUS =================
        status = "Shortlisted" if score > 60 else "Rejected"

        # ================= STORE DATA =================
        cursor.execute("""
            INSERT INTO resumes 
            (job_id, candidate_name, resume_text, match_score, 
             matched_skills, missing_skills, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            job_id,
            candidate_name,
            resume_text,
            score,
            matched_skills_str,
            missing_skills_str,
            status
        ))

        db.commit()

        return redirect(f"/results/{job_id}")

    return render_template("upload_resume.html", job_id=job_id)

# ================= RESULTS =================
@app.route("/results/<int:job_id>")
def results(job_id):
    cursor.execute("""
        SELECT * FROM resumes
        WHERE job_id=%s
        ORDER BY match_score DESC
    """, (job_id,))
    results = cursor.fetchall()

    return render_template("results.html", results=results)

# ================= ALL CANDIDATES =================
@app.route("/all-candidates")
def all_candidates():
    status_filter = request.args.get("status")

    base_query = """
        SELECT resumes.candidate_name,
               resumes.match_score,
               resumes.status,
               jobs.title
        FROM resumes
        JOIN jobs ON resumes.job_id = jobs.id
    """

    if status_filter == "shortlisted":
        base_query += " WHERE resumes.status = 'Shortlisted'"

    base_query += " ORDER BY resumes.match_score DESC"

    cursor.execute(base_query)
    candidates = cursor.fetchall()

    return render_template("all_candidates.html", candidates=candidates)

# ================= RUN SERVER =================
if __name__ == "__main__":
    app.run(debug=True)