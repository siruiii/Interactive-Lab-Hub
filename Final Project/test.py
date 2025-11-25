import qwiic_rfid
import time
import sys

def run_example():

    print("\nSparkFun Qwiic RFID Reader Example 1")
    my_RFID = qwiic_rfid.QwiicRFID()

    if my_RFID.begin() == False:
        print("\nThe Qwiic RFID Reader isn't connected to the system. Please check your connection", file=sys.stderr)
        return
    
    print("\nReady to scan some tags!")
    
    while True:
        tag_id = my_RFID.get_tag()
        
        if tag_id != "000000":
            print("\n Tag scanned!")
            print("Tag ID: " + tag_id)

            scan_time = my_RFID.get_prec_req_time()
            print("Scanned " + str(scan_time) + " seconds ago")
        
        time.sleep(1)

if __name__ == '__main__':
    try:
        run_example()
    except (KeyboardInterrupt, SystemExit) as exErr:
        print("\nEnding Example 1")
        sys.exit(0)
