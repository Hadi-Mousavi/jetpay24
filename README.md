# JetPay24

**JetPay24** (`جت‌پی‌۲۴`) is a Django-based web application for international payment services designed for students and families.

The project is actively under development and currently focuses on order submission, document upload, admin management, and public order tracking.

## Overview

JetPay24 helps users request international payment services through a simple Persian-language web interface. Users can submit payment orders, upload required documents, and track their order status using a public tracking code.

Current supported services include:

- University application fee payments
- University tuition payments
- TOEFL registration payments
- GRE registration payments
- International money transfers

## Features

- Persian landing page for JetPay24 services
- Order submission form
- Secure document upload validation
- Automatic public tracking code generation
- Public order tracking page
- Django admin panel for order management
- Admin search and filtering for orders
- Persian UI text and RTL layout

## Screenshots

Screenshots will be added as the UI stabilizes.

- Landing page
- Order submission page
- Order success page with tracking code
- Public tracking page
- Django admin order list

## Tech Stack

- Python
- Django 4.2
- SQLite for local development
- Bootstrap RTL
- Bootstrap Icons
- Vazirmatn Persian font

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd JetPay24
```

Create and activate a virtual environment:

```bash
python -m venv venv
```

On Windows:

```bash
venv\Scripts\activate
```

On macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install django
```

> Note: A dedicated dependency file such as `requirements.txt` is planned for a future development phase.

## Running Locally

Apply database migrations:

```bash
python manage.py migrate
```

Create an admin user:

```bash
python manage.py createsuperuser
```

Start the development server:

```bash
python manage.py runserver
```

Open the project locally:

- Website: `http://127.0.0.1:8000/`
- Order form: `http://127.0.0.1:8000/order/`
- Order tracking: `http://127.0.0.1:8000/tracking/`
- Admin panel: `http://127.0.0.1:8000/admin/`

## Project Structure

```text
JetPay24/
├── config/                 # Django project settings and root URL configuration
├── orders/                 # Order model, forms, views, admin, URLs, migrations
├── pages/                  # Public landing page views and URLs
├── templates/
│   ├── orders/             # Order form, success, and tracking templates
│   └── pages/              # Landing page template
├── manage.py               # Django management entry point
└── README.md
```

## Future Roadmap

- Production-ready settings and environment-based configuration
- Dependency file and deployment documentation
- Improved order tracking with status history
- Dedicated service detail pages
- Contact page with backend processing
- FAQ page
- Blog system for SEO and educational content
- SEO metadata, sitemap, and structured data
- Admin workflow improvements and reporting
- Future AI assistant integration
- Future Android app/API integration

## Development Status

JetPay24 is an active project under development. The current version is suitable for local development and feature iteration, but production deployment requires additional security, configuration, testing, and infrastructure work.
