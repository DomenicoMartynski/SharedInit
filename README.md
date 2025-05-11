# SharedInit - LAN File Sharing Application

SharedInit is a modern, user-friendly file sharing application designed for local networks. It provides a seamless way to share files between devices on the same network, with support for various file types and automatic file handling.

## Features

- 🚀 **Easy to Use**: Simple and intuitive user interface
- 🔄 **Real-time Updates**: Instant file reception notifications
- 📱 **Cross-Platform**: Works on Windows, macOS, and Linux
- 🔒 **Local Network Only**: Files stay within your network
- 🎨 **Modern UI**: Clean and responsive design
- 📦 **Multiple File Types**: Support for various file formats
- 🔍 **Auto-Detection**: Automatically finds other devices on the network

## Architecture

The application uses a modern microservices architecture:

- **Streamlit Frontend** (`app.py`): Handles the user interface and file management
- **Flask Backend** (`file_server.py`): Manages file uploads and processing
- **Process Manager** (`sharedinit.py`): Coordinates and monitors both services

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/SharedInit.git
cd SharedInit
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

Simply run:
```bash
python sharedinit.py
```

This will:
1. Start the Flask server for file handling
2. Launch the Streamlit interface
3. Monitor both services for stability

The application will be available at:
- Streamlit UI: http://localhost:8501
- Flask API: http://localhost:8502

## File Structure

```
SharedInit/
├── app.py              # Streamlit frontend application
├── file_server.py      # Flask backend for file handling
├── sharedinit.py       # Main process manager
├── requirements.txt    # Python dependencies
├── downloads/         # Directory for received files
└── img/              # Application images and assets
```

## Supported File Types

### Main Applications
- 🎨 **Adobe Creative Suite** (Photoshop, Illustrator, InDesign, etc.)
- 💼 **Microsoft Office** (Word, Excel, PowerPoint, etc.)
- 🏗️ **Autodesk** (AutoCAD, Revit, 3ds Max, etc.)

### Other Formats
- 🖼️ **Images** (JPG, PNG, RAW, etc.)
- 🎥 **Media** (MP4, MP3, etc.)
- 📦 **Archives** (ZIP, RAR, etc.)

## Development

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setting up the development environment

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install development dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application in development mode:
```bash
python sharedinit.py
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Streamlit for the amazing web framework
- Flask for the robust backend framework
- All contributors who have helped shape this project
