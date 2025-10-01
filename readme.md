# 🏠 Real Estate Scraper (Educational Project)

⚠️ **Disclaimer**  
This project is developed **for educational and private use only**.  
It demonstrates how to integrate web scraping, data processing, and WhatsApp message delivery into a single application.  
Many of the listed websites explicitly forbid automated scraping in their Terms of Service. Please respect their policies and **do not use this project for commercial purposes**.  

---

## 🚀 Features
- Scrapes listings from Swiss real estate websites  
- Deduplication with a SQLite database  
- Sends results automatically to WhatsApp group chats  
- Modular design: easy to add new scrapers for other sites  

---

## 🛠️ Run Locally

1. Clone the repository  
2. (Optional but recommended) Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux / macOS
   venv\Scripts\activate      # Windows

Install dependencies:
pip install -r requirements.txt


Run the application:
python entrypoint.py

## 🐳 Run with Docker / Kubernetes
TODO: Docker Compose and Kubernetes manifests will be added later.

```
[Kubernetes Cluster]
   |
   ├── Master Node (control plane)
   |
   └── Worker Node(s)
         ├── Pod: Scraper
         │      └── Container: real-estate-scraper
         │            ↘ writes listings
         │
         ├── Pod: Database
         │      └── Container: postgres (PVC for storage)
         │
         └── Pod: WhatsApp Service
                └── Container: whatsapp-service
                        ↘ sends messages via WhatsApp
```

<img width="402" height="717" alt="image" src="https://github.com/user-attachments/assets/35c9a574-5e9e-4d52-b691-ed9a858ee8d0" />

## 📌 Future Add-ons

Categorization (e.g., Genossenschaftswohnungen, MFH, Einfamilienhaus, WG-Zimmer Suche)

Google Maps integration

Price analyzer (€/m², taxes, consumption, comparisons)

Auto-delete outdated listings

## 🌐 (Future) Target Websites

This project is built with connectors for:

newhome.ch
homegate.ch
flatfox.ch
immoscout24.ch
vermietungen.stadt-zuerich.ch
betterhomes.ch
erstbezug.ch
home.ch
immostreet.ch
students.ch
urbanhome.ch
pwg.ch
realadvisor.ch
properstar.ch
sherlockhomes.ch
properti.com
weegee.ch
wgzimmer.ch

## 📜 License

This code is distributed under the MIT License.
Use it at your own risk. No warranties provided.
