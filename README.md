# SharedInit - LAN File Sharing App

![SharedInit Logo](img/SharedInitlogo.png)

An App created as part of the Engineer's Thesis. The App allows multiple Computers to connect to each other, share files and automatically opens the 
default app bound to the extension of the sent file.
A  Streamlit application that allows users to share files within a Local Area Network (LAN).

## Features

- Share files with other users in the same LAN
- Automatic file opening with default applications when receiving files
- Simple and intuitive user interface
- Real-time file sharing
- Device discovery and connection

## Installation

1. Make sure you have Python 3.7+ installed on your system
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Setting Up the App

1. Run the application on your PC:
   ```bash
   streamlit run app.py
   ```

2. The app will display your local IP address. This is your host address.

### Connecting Other Devices

To share files between devices, each device needs to:

1. Have Python 3.7+ installed
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   streamlit run app.py
   ```

### Sharing Files

1. Once multiple devices are running the app:
   - Go to the "Connected Devices" page (📱 icon in sidebar)
   - You'll see other devices running the app
   - Click "Connect" to open their file sharing interface

2. To share files:
   - Click on "Choose a file to share" to select a file
   - The file will be uploaded and available for other users to download
   - When someone downloads a file, it will automatically open with the default application for that file type

## Notes

- All devices must be connected to the same LAN network
- Each device that wants to participate in file sharing must run the app
- The app creates two folders:
  - `shared_files`: Contains files that are shared
  - `received_files`: Contains files that are downloaded
- Files are automatically opened with the default application when downloaded
- Make sure port 8501 is not blocked by your firewall
