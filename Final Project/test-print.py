from escpos.printer import Usb

# --- The content to be printed, using standard text and commands ---

# Initialize the printer (assuming a USB connection).
# You may need to find your printer's correct USB Vendor (VID) and Product (PID) IDs.
# Run 'lsusb' in the terminal to find them (e.g., 0x04b8, 0x0202).
try:
    # 1. Connect to the USB Printer (Replace with your actual VID/PID)
    # The 'in_ep' and 'out_ep' might also be necessary. Check your printer manual or trial and error.
    p = Usb(0x04b8, 0x0202, 0, 0x81, 0x02) # Example: Epson TM-T88V IDs

    # 2. Initialize the Printer
    p.set(align='center', font='b', height=1, width=1)
    
    # 3. Print Content
    p.text("Hello World\n")
    p.text("\n\n\n\n") # Extra lines for spacing
    
    # 4. Perform Partial Cut (The library handles the raw command for you)
    p.cut()
    
    print("Successfully printed receipt using python-escpos.")

except Exception as e:
    # If using USB, you might get a 'No device found' error if the IDs are wrong or permissions are an issue.
    print(f"An error occurred: {e}")