# Project Setup

This project uses Python **virtual environment (venv)** to keep dependencies consistent.

1. **Clone the repo**
    
    `git clone https://github.com/haritsbachtiar/social-media-crawling.git`
    
    `git cd social-media-crawling`

2. **Create venv**

    `python -m venv venv`

3. **Activate venv**
    
    Windows
    
    `venv\Scripts\activate`

    MacOS / Linus
    
    `source venv/bin/activate`

4. **Install dependencies**
    
    `pip install -r requirements.txt`

5. **Download the NLTK corpora**

    `python -m textblob.download_corpora`

6. **Run the project**
    
    `uvicorn main:app --reload`