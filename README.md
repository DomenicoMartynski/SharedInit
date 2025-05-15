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

### Normal Usage (Recommended)
Simply double-click the appropriate launcher for your platform:
- macOS: `SharedInit - macOS Launcher.command`
- Windows: `SharedInit - Windows Launcher.vbs`
- Linux: `SharedInit - Linux Launcher.sh`

The launcher will:
1. Start the Flask server for file handling
2. Launch the Streamlit interface
3. Run both services in the background

The application will be available at:
- Streamlit UI: http://localhost:8501
- Flask API: http://localhost:8502

To stop the application, simply run the launcher again - it will detect that the app is running and shut it down.

### Development Mode
If you're developing the application, you can run it directly:

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the Flask server:
```bash
python file_server.py
```

4. In a separate terminal, start the Streamlit app:
```bash
streamlit run app.py
```

## File Structure

```
SharedInit/
├── app.py              # Streamlit frontend application
├── file_server.py      # Flask backend for file handling
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
python file_server.py
streamlit run app.py
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

## Autostart Setup

### macOS
1. Edit the `com.sharedinit.app.plist` file and replace `ABSOLUTE_PATH_TO_APP_DIRECTORY` with the full path to your app directory
2. Copy the plist file to your LaunchAgents directory:
   ```bash
   cp com.sharedinit.app.plist ~/Library/LaunchAgents/
   ```
3. Load the service:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.sharedinit.app.plist
   ```
4. To stop the service:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.sharedinit.app.plist
   ```

### Windows
1. Run `toggle_windows_autostart.bat` as administrator
2. This will create a shortcut in your Windows Startup folder if autostart is not already enabled, or remove it if it is enabled
3. The app will start automatically when you log in if autostart is enabled
4. To stop autostart, simply run `toggle_windows_autostart.bat` again

### Linux
1. Edit the `sharedinit.service`