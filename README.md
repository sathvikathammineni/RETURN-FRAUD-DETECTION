# Return Fraud Detection System

A web-based application built using Python and Flask to assess return requests, identify potentially high-risk cases, and help staff review suspicious returns.

## Project Overview

The Return Fraud Detection System helps manage product return requests by calculating a risk score from selected return-related factors. Based on the score, a request is either automatically approved or sent for staff review.

## Features

* Customer registration and login
* Return request submission
* Risk score calculation
* Low Risk and High Risk classification
* Automatic approval for low-risk requests
* Staff review for high-risk requests
* Staff dashboard to view return requests
* Accept or reject return requests
* Tracking IDs for return requests
* Customer request status tracking

## Technologies Used

* **Python** — application logic
* **Flask** — web framework
* **HTML** — page structure
* **CSS** — page styling
* **SQLite** — local database
* **Git and GitHub** — version control and project hosting

## Risk Assessment

The application calculates a risk score using configured rules, which may consider:

* Item value
* Customer account age
* Previous return requests
* Return reason
* New payment card indicator

The score is used to classify requests as Low Risk or High Risk. High-risk requests are sent for staff review.

**Note:** This is a demonstration project. Risk scores are rule-based and should not be treated as proof of fraud.

## Project Structure

```text
RETURN-FRAUD-DETECTION/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── static/
│   └── style.css
└── templates/
    ├── dashboard.html
    ├── login.html
    ├── register.html
    └── staff_dashboard.html
```

## Installation and Setup

### 1. Install Python

Install Python on your computer if it is not already installed.

### 2. Clone the repository

```bash
git clone https://github.com/sathvikathammineni/RETURN-FRAUD-DETECTION.git
cd RETURN-FRAUD-DETECTION
```

### 3. Create a virtual environment

**Windows:**

```powershell
python -m venv venv
```

### 4. Activate the virtual environment

```powershell
.\venv\Scripts\Activate.ps1
```

### 5. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 6. Run the application

```powershell
python app.py
```

### 7. Open the application

Visit this address in your browser:

```text
http://127.0.0.1:5000
```

## Database

The application uses SQLite to store application data locally. The database file is excluded from the Git repository, so a local database may be created or initialized when the application runs, depending on the implementation.

Do not commit real customer information, passwords, or secret keys.

## Future Improvements

* Machine learning-based fraud risk prediction
* Improved staff analytics and reporting
* Stronger authentication and authorization
* Audit logs for staff decisions
* Secure deployment to a web hosting platform

## Disclaimer

This project is intended for educational and demonstration purposes. Its rule-based scores are not a definitive determination that a customer has committed fraud.

## Author

Developed as a student project to demonstrate web development, database integration, and rule-based return risk assessment.
