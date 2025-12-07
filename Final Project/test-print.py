import win32print
import win32api

# --- The content to be printed, using ESC/POS commands ---

# We construct the receipt data clearly with line breaks.
data_to_print_bytes = (
    b'\x1B\x40'          # 1. Initialize Printer (ESC @) - Resets settings.
    
    # --- Data to Print ---
    b'Hello World'       # Your main text
    b'\x0A'              # **New Line / Line Feed (Required)**
    b'\x0A'  # Example Separator
    b'\x0A'              # New Line
    b'\x0A\x0A\x0A\x0A'  # 2. Add extra Line Feeds to push paper out
    
    # --- Cut Command ---
    b'\x1D\x56\x01'      # 3. Partial Cut (GS V 1)
)

try:
    # 1. Get the default printer name (POS-80)
    default_printer = win32print.GetDefaultPrinter()
    
    # 2. Open a printer handle
    hPrinter = win32print.OpenPrinter(default_printer)
    
    # 3. Start a document job (still using "RAW" data type)
    hJob = win32print.StartDocPrinter(
        hPrinter, 
        1, 
        ("POS Hello World Receipt Fixed", None, "RAW") 
    )
    
    # 4. Start a page
    win32print.StartPagePrinter(hPrinter)
    
    # 5. Send the ESC/POS data (must be bytes)
    win32print.WritePrinter(hPrinter, data_to_print_bytes)
    
    # 6. End the page and the document
    win32print.EndPagePrinter(hPrinter)
    win32print.EndDocPrinter(hPrinter)
    
    # 7. Close the printer handle
    win32print.ClosePrinter(hPrinter)
    
    print(f"Successfully sent revised POS receipt commands to: {default_printer}")
    
except Exception as e:
    print(f"An error occurred: {e}")