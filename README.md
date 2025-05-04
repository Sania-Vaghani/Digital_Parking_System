# Digital Parking System

A Python-based system for managing digital parking, including user authentication, parking slot management, and SMS notifications via Twilio. This project uses a MySQL database for data storage and is designed for easy local deployment and testing.

## Features
- User registration and login
- Parking slot booking and management
- Twilio SMS notifications
- MySQL database integration

## Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/Sania-Vaghani/Digital_Parking_System.git
   ```
2. **Navigate to the project directory:**
   ```sh
   cd Digital_Parking_System
   ```
3. **Create a virtual environment and activate it:**
   ```sh
   python -m venv venv
   venv\Scripts\activate   # On Windows
   ```
4. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
5. **Create a `.env` file** with your credentials (see Configuration below).

## Usage

Run the main application:
```sh
python saniya.py
```

Access the system at `http://localhost:5000` (if it’s a web app).

## Configuration

Create a `.env` file in the project root with the following variables:
```
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number

DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_db_password
DB_NAME=parking_system
```

## Screenshots
_Add screenshots or UI images here if available._

## Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License
This project is licensed under the MIT License.

## Contact
Created by [Sania-Vaghani](https://github.com/Sania-Vaghani). Feel free to reach out for collaboration or questions.