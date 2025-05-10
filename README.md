#  SharedInit - LAN File Sharing App
An App created as part of the Engineer's Thesis. The App allows multiple Computers to connect to each other, share files and automatically opens the 
default app bound to the extension of the sent file.
A  Streamlit application that allows users to share files within a Local Area Network (LAN).

## Features

- Share files with other users in the same LAN
- Automatic file opening with default applications when receiving files
- Simple and intuitive user interface
- Real-time file sharing

## Installation

1. Make sure you have Python 3.7+ installed on your system
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```bash
   streamlit run app.py
   ```

2. The app will display your local IP address. Share this IP address with other users in your LAN.

3. Other users can access the app by entering your IP address in their web browser:
   ```
   http://<your-ip-address>:8501
   ```

4. To share files:
   - Click on "Choose a file to share" to select a file
   - The file will be uploaded and available for other users to download
   - When someone downloads a file, it will automatically open with the default application for that file type

## Notes

- Make sure all users are connected to the same LAN network
- The app creates two folders:
  - `shared_files`: Contains files that are shared
  - `received_files`: Contains files that are downloaded
- Files are automatically opened with the default application when downloaded
