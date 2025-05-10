import streamlit as st

def main():
    st.title("📚 Documentation")
    
    st.markdown("""
    ## About LAN File Sharing App
    
    This application allows you to easily share files between devices on your local network. 
    It's perfect for teams working in the same office or students collaborating on projects.
    
    ### Key Features
    - 🚀 Instant file sharing between devices
    - 🔄 Automatic file opening on receipt
    - 🔍 Real-time device discovery
    - 🛡️ Secure local network transfer
    - 📱 Cross-platform support (Windows, macOS, Linux)
    
    ### How It Works
    1. Start the app on all devices that need to share files
    2. The app automatically discovers other devices running the application
    3. Select files to share from your device
    4. Files are instantly transferred to the receiving device
    5. Received files can be opened automatically with their default applications
    
    ## Currently Supported File Formats
    
    ### 🎨 Adobe Applications
    | Application | File Extensions | Description |
    |------------|----------------|-------------|
    | Photoshop | .psd | Photoshop Document |
    | Illustrator | .ai | Adobe Illustrator Artwork |
    | InDesign | .indd | InDesign Document |
    | Acrobat | .pdf | Portable Document Format |
    | Premiere Pro | .prproj | Premiere Pro Project |
    | After Effects | .aep | After Effects Project |
    | Lightroom | .lrcat | Lightroom Catalog |
    | Audition | .sesx | Audition Session |
    
    ### 💼 Microsoft Office
    | Application | File Extensions | Description |
    |------------|----------------|-------------|
    | Word | .doc, .docx | Word Document |
    | Excel | .xls, .xlsx | Excel Spreadsheet |
    | PowerPoint | .ppt, .pptx | PowerPoint Presentation |
    | Publisher | .pub | Publisher Document |
    | Visio | .vsd | Visio Drawing |
    | Access | .mdb, .accdb | Access Database |
    | Outlook | .pst, .msg | Outlook Data File |
    | OneNote | .one | OneNote Notebook |
    
    ### 🏗️ Autodesk
    | Application | File Extensions | Description |
    |------------|----------------|-------------|
    | AutoCAD | .dwg, .dxf | AutoCAD Drawing |
    | Revit | .rvt, .rfa | Revit Project/Family |
    | 3ds Max | .max | 3ds Max Scene |
    | Maya | .ma, .mb | Maya Scene |
    | Inventor | .ipt, .iam | Inventor Part/Assembly |
    | Civil 3D | .dwg | Civil 3D Drawing |
    | Fusion 360 | .f3d | Fusion 360 Design |
    | Navisworks | .nwd | Navisworks Document |
    
    
    #### 🖼️ Images
    - Common formats: JPG, PNG, GIF, BMP, TIFF, SVG, WebP, ICO
    - RAW formats: .raw, .cr2, .nef, .arw, .dng
    
    #### 🎥 Media
    - Video: MP4, AVI, MOV, WMV, FLV, MKV
    - Audio: MP3, WAV, FLAC, AAC, M4A, WMA
    
    #### 📦 Archives
    - Compression: ZIP, RAR, 7Z
    - Backup: TAR, GZ, BZ2
    - Project files and backups
    
    
    ### Usage Tips
    - Keep the app running on all devices that need to share files
    - Ensure your firewall allows the app to communicate on the network
    - Files are automatically saved to the `received_files` directory
    - Maximum file size: 200MB
    
    ## Troubleshooting
    
    ### Common Issues
    1. **Devices not showing up**
       - Check if all devices are on the same network
       - Ensure the app is running on all devices
       - Check firewall settings
    
    2. **Files not transferring**
       - Verify file size is under 200MB
       - Check if the file type is supported
       - Ensure receiving device has enough storage space
    
    3. **Files not opening automatically**
       - Check if the file type has a default application set
       - Verify file permissions on the receiving device
    
    ### Need Help?
    If you encounter any issues not covered here, please:
    1. Check the console output for error messages
    2. Ensure all devices are running the latest version
    3. Try restarting the app on all devices
    """)

if __name__ == "__main__":
    main() 