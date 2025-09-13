# SecureShare 🔐

SecretShare is a lightweight Flask-based web application that lets you securely share sensitive text or files via expiring links. Links can expire after a certain time period or a fixed number of views, ensuring privacy and control.

---

## ✨ Features

* **Share Secrets Securely**: Paste text or upload a file to generate a one-time secret link.
* **Custom Expiry Options**: Expire links after *n* minutes/hours/days or after *n* views.
* **Support for Text + Files**: Share plain text, code snippets, or encrypted files.
* **Dark/Light Mode**: Persistent theme toggle with localStorage support.
* **Modern UI**: Responsive TailwindCSS-based interface with smooth animations.
* **Automatic Cleanup**: Links auto-expire and files are deleted from the server.

---

## 🛠️ Tech Stack

* **Backend**: Python, Flask, SQLAlchemy
* **Frontend**: TailwindCSS, Vanilla JS
* **Database**: SQLite (default, can be swapped with PostgreSQL/MySQL)

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/rahul-1809/SecureShare.git
cd secretshare
```

### 2. Create Virtual Environment & Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

### 3. Setup Database

```bash
flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
```

### 4. Run the Application

```bash
flask run
```

Visit: [http://localhost:5000](http://localhost:5000)

---

## 📂 Project Structure

```
secretshare/
├── app.py              # Main Flask app
├── templates/          # Jinja2 templates (HTML)
│   ├── base.html       # Base layout with navbar & theme toggle
│   ├── index.html      # Landing page with form
│   ├── result.html     # Short URL result page
│   ├── content.html    # View text + download file
│   ├── file_page.html  # File-only view page
│   └── expired.html    # Expired/invalid link page
├── static/             # Optional static assets (CSS, JS)
├── uploads/            # Encrypted file storage (auto-deleted)
├── links.db            # SQLite database
└── requirements.txt    # Python dependencies
```

---

## 🔧 Configuration

Environment variables:

```bash
SECRET_KEY=your-secret-key
FILE_KEY=optional-fernet-key
```

* `SECRET_KEY`: Used by Flask sessions & Fernet key derivation (default: `dev-secret-key`).
* `FILE_KEY`: (Optional) Provide a custom Fernet key for encryption.

---

## 🖼️ Screenshots

* Landing page with call-to-action
* Secret creation form
* Result page with short URL
* Expired link view

*(Add screenshots here once hosted)*

---

## 🚀 Future Enhancements

* 🔑 Password-protected secrets
* 📊 Analytics for link usage
* 📧 Email/Slack integration for sharing
* ☁️ Deploy on Render/Heroku/Netlify

---

## 📜 License

This project is licensed under the MIT License.

---

### 👨‍💻 Author

Developed by **Rahul** ✨
