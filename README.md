# E-Commerce Platform

A modern e-commerce platform built with Flask, featuring a clean UI and robust backend functionality.

## Features

- User authentication (login/register)
- Product browsing and search
- Shopping cart functionality
- Wishlist management
- Seller dashboard
- Order management
- User profiles

## Tech Stack

- Backend: Flask (Python)
- Frontend: HTML, CSS (Tailwind), JavaScript
- Database: SQLite
- Authentication: Flask-Login

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd e-commerce
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
npm install
```

4. Set up environment variables:
- Copy `instance/config.example.py` to `instance/config.py`
- Update configuration values

5. Initialize database:
```bash
flask db upgrade
```

6. Run the application:
```bash
flask run
```

## Project Structure

```
├── app.py                  # Core application logic
├── config.py              # Base configuration
├── instance/              # Instance-specific configs
├── static/               # Static assets
│   ├── css/
│   ├── js/
│   ├── images/
│   └── uploads/
└── templates/            # Jinja2 templates
    ├── auth/
    ├── users/
    └── sellers/
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License. 