from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
from datetime import datetime, timedelta
import argparse
import sys
import ast

def parse_args():
    parser = argparse.ArgumentParser(description='action.yml arguments')
    parser.add_argument('--username', type=str, help='Username (case-insensitive)')
    parser.add_argument('--password', type=str, help='Password (case-insensitive)')
    parser.add_argument('--building_name', type=str, help='Select a Building')
    parser.add_argument('--floor_prefix', type=str, help='Floor prefix for seat labels, e.g., TD05')
    parser.add_argument('--floor_label', type=str, help='Floor label for dropdown, e.g., 05')
    parser.add_argument('--workstation', type=str, help='WorkPoint-WorkStation')
    parser.add_argument('--workstation_backup', type=str, default='[]', required=False, help='WorkPoint-WorkStation-Backup')
    parser.add_argument('--advance_reservation', action='store_true', required=False, help='Book 4 weeks and one day ahead')
    return parser.parse_args()

class archibus_scheduler():
    def __init__(self, args):
        self.username = args.username
        self.password = args.password
        self.building_name = args.building_name.replace("-", " ")
        self.floor_prefix = args.floor_prefix   # NEW: for seat labels
        self.floor_label = args.floor_label     # NEW: for dropdown
        self.workstation = args.workstation
        self.workstation_backup = ast.literal_eval(args.workstation_backup)
        self.advance_reservation = args.advance_reservation

        self.current_date = datetime.now().strftime("%Y-%m-%d")

        if self.advance_reservation:
            self.next_month = (datetime.now() + timedelta(weeks=4, days=1)).strftime("%Y-%m-%d")
        else:
            self.next_month = (datetime.now() + timedelta(weeks=4)).strftime("%Y-%m-%d")

        self.next_month_day = str(int(self.next_month[-2:]))  # day part, unpadded
        self.seat_date = datetime.strptime(self.next_month, '%Y-%m-%d').strftime("Choose %A, %B %d, %Y")
        suffix = "th" if 11 <= int(self.next_month_day) <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(int(self.next_month_day) % 10, "th")
        self.seat_date = self.seat_date.replace(f"{int(self.next_month_day):02d}", f"{int(self.next_month_day)}{suffix}", 1)

        if self.workstation == '101' and self.floor_prefix == 'JT07' and self.username != 'EVANJUS':
            raise Exception('Workstation is unavailable.')


    def setup(self):
        service = Service(ChromeDriverManager().install())
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument("--disable-notifications")

        SELENIUM_GRID_URL = 'http://localhost:4444/wd/hub'
        self.driver = webdriver.Remote(
            command_executor=SELENIUM_GRID_URL,
            options=chrome_options,
            keep_alive=True
        )

        self.driver.implicitly_wait(15)
        self.wait = WebDriverWait(self.driver, 10)

    def popups(self):
        try:
            reassignment = self.driver.find_element(By.CSS_SELECTOR, '[class*="DontShowButton"]')
            reassignment.click()
        except NoSuchElementException:
            pass
        try:
            reassignment = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Close')]")
            reassignment.click()
        except NoSuchElementException:
            pass
        try:
            reassignment = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Yes')]")
            reassignment.click()
        except NoSuchElementException:
            pass

    def seat_selection(self):
        seat_options = [self.workstation]
        seat_options.extend(self.workstation_backup)
    
        for seat in seat_options:
            padded_seat = seat.zfill(3)
    
            workstation_formats = [
                f"//p[text() = '{seat} - Primary Individual Open/Primaire, individuel et ouvert']",
                f"//p[text() = '{self.floor_prefix}-{padded_seat} - Secondary Individual/Secondaire et individuel']",
                f"//p[contains(text(), '{self.floor_prefix}-{padded_seat}')]"
            ]
    
            for format in workstation_formats:
                try:
                    input_selected_seat = self.driver.find_element(By.XPATH, format)
                    print(f"Seat Selected: {input_selected_seat.text}")
                    input_selected_seat.click()
                    return  # stop after first valid seat
                except:
                    print(f"Seat Unavailable (XPath tried): {format}")
    
        raise NoSuchElementException("No available seat found")


    def actions(self):
        self.setup()
        self.driver.get("https://pathfinder.horizantsolutions.com/archibus/schema/ab-products/essential/workplace/index.html")

        input_username = WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.ID, "logon-user-input"))
        )
        input_username.send_keys(self.username)

        input_password = self.driver.find_element(by=By.ID,value='logon-password-input')
        input_password.send_keys(self.password)

        input_log_in = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="logon-sign-in-btn"]')
        input_log_in.click()
        print(f"User Logged In")

        try:
            input_workspace_booking = self.driver.find_element(By.XPATH, f"//div[contains(text(), 'CREATE WORKSPACE BOOKING')]")
            input_workspace_booking.click()
            print(f'Loading Create Workspace Booking')
            time.sleep(10)
        except NoSuchElementException:
            print("Pre-loaded into Create Workstation Booking")

        print(f"Primary building XPath: //div[contains(text(), '{self.building_name}')]")
        input_building = self.driver.find_element(By.XPATH, f"//div[contains(text(), '{self.building_name}')]")
        input_building.click()
        print(f'Selected Building')
        time.sleep(2)

        try:
            input_workspace_booking = self.driver.find_element(By.XPATH, f"//h3[contains(text(), 'Workspaces')]")
            input_workspace_booking.click()
            print(f'Loading Create Workspace Booking')
            time.sleep(2)
            self.popups()
        except NoSuchElementException:
            print("Pre-loaded into Building Booking")
            time.sleep(2)

        try:
            input_building_search = self.driver.find_element(By.XPATH, f"//div[contains(text(), 'Buildings')]")
            input_building_search.click()
            print(f'Searching for Building in Dropdown')
            time.sleep(30)
            self.popups()

            print(f"Fallback building XPath: //div[text()='{self.building_name}']")
            input_building = self.driver.find_element(By.XPATH, f"//div[text()='{self.building_name}']")
            self.driver.execute_script("arguments[0].click();", input_building)
            print(f'Selected Building')
            time.sleep(2)

        except NoSuchElementException as e:
            print(f'Exception: {e}')
            print("Building Already Selected")

        self.popups()

        calendar = self.driver.find_element(By.ID, 'startData_icon')
        calendar.click()

        input_next_month = self.driver.find_element(By.XPATH, "//button[@aria-label = 'Select next month']")
        input_next_month.click()

        date = self.driver.find_element(By.XPATH, f"//div[@aria-label='{self.seat_date}']")
        actions = ActionChains(self.driver)
        actions.move_to_element(date).click().perform()
        print(f'Date Selected: {self.next_month}')
        time.sleep(2)

        input_floor = self.driver.find_element(By.XPATH, f"//div[text() = '{self.floor_label}']")
        input_floor.click()
        print(f'Floor Selected: {self.floor_label}')
        time.sleep(2)

        input_search = self.driver.find_element(By.XPATH, "//button[text() = 'Search']")
        input_search.click()
        time.sleep(2)

        self.seat_selection()
        time.sleep(2)

        input_book_seat = self.driver.find_element(By.XPATH, "//button[text() = 'Book']")
        input_book_seat.click()
        time.sleep(2)
        print('Select Book Seat')

        input_book_myself = self.driver.find_element(By.XPATH, "//span[text() = 'Myself']")
        input_book_myself.click()
        time.sleep(2)
        print("Booking for 'Myself'")

        input_book_seat = self.driver.find_element(By.XPATH, "//button[text() = 'BOOK']")
        input_book_seat.click()
        time.sleep(2)

        self.popups()
        input_confirmation = self.driver.find_element(By.XPATH, "//button[contains(text(),'GO TO MAIN')]")
        input_confirmation.click()
        print("Confirmation seat is booked")

        self.driver.close()

if __name__ == "__main__":
    args = parse_args()
    scheduler = archibus_scheduler(args)
    scheduler.actions()
