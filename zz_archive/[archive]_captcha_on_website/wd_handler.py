import time
from urllib.parse import urljoin, urlparse
import unicodedata

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium_stealth import stealth

import numpy as np
import requests
from PIL import Image
from skimage.transform import resize
from io import BytesIO

from difflib import SequenceMatcher

class Webdriver_Handler:
    def __init__(self, website_url, available_models):
        self.available_models = available_models

        options = webdriver.ChromeOptions()
        options.add_argument('disable-infobars')
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('window-size=500,800')

        self.website_url = website_url

        self.timeout = 3

        self.wd = None
        try:
            self.wd = webdriver.Chrome("F:/python/chromedriver/chromedriver.exe", options=options)
        except:
            print("chromedriver not found, trying different loc")
        if self.wd == None:
            try:
                self.wd = webdriver.Chrome("C:/Users/V61XNRQ/Desktop/Personal/apps/chromedriver_win32/chromedriver.exe", options=options)
            except:
                print("chromedriver not found")
                exit(-1)
        self.wd.implicitly_wait(self.timeout)
        stealth(
            self.wd,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

        self.widget_state = 0

    
    def normalize_string(self, string):
        ratios = []
        for model_name in self.available_models:
            ratios.append(SequenceMatcher(a=string,b=model_name).ratio())
        print(ratios)
        if max(ratios) > 0.5:
            return self.available_models[np.argmax(np.array(ratios))]
        return "--unidentified--"


    def focus_on_root_frame(self):
        self.wd.switch_to.default_content()
        self.widget_state = 0
        print("Switched to root iframe")

    def focus_on_container_frame(self):
        WebDriverWait(self.wd, self.timeout).until(EC.frame_to_be_available_and_switch_to_it((By.XPATH,"//iframe[contains(@src,'hcaptcha.com') and contains(@title,'checkbox')]")))
        self.widget_state = 1
        print("Switched to hCaptcha Container iframe")

    def focus_on_challenge_frame(self):
        WebDriverWait(self.wd, self.timeout).until(EC.frame_to_be_available_and_switch_to_it((By.XPATH,"//iframe[contains(@src,'hcaptcha.com') and contains(@title,'Main content')]")))
        self.widget_state = 2
        print("Switched to hCaptcha Challenge iframe")

    def focus_on_frame(self, target_frame):
        if target_frame == self.widget_state:
            return
        
        if target_frame == 0:
            self.focus_on_root_frame()
            return
        if target_frame == 1:
            if self.widget_state == 2:
                self.focus_on_root_frame()
            self.focus_on_container_frame()
            return
        if target_frame == 2:
            self.focus_on_root_frame()
            self.focus_on_challenge_frame()
            return


    def load_captcha(self):        
        self.wd.get(self.website_url)
        print("Loaded Website")

        try:
            self.focus_on_frame(1)
        except:
            print("No hCaptcha iframe found")
            return
        
        # click hCaptcha container
        WebDriverWait(self.wd, self.timeout).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div"))).click()
        print("Launched hCaptcha")


    def get_string(self):
        self.focus_on_frame(2)

        print("Trying to get captcha string")
        try:
            captcha_str = self.wd.find_element(By.XPATH, "//span[contains(text(),'click') and contains(text(),'image')]").text
        except:
            captcha_str = self.wd.find_element(By.XPATH, "//span[contains(text(),'click') and contains(text(),'image')]").text
        captcha_str = captcha_str.replace("Please click each image containing an ","")
        captcha_str = captcha_str.replace("Please click each image containing a ","")
        captcha_str = self.normalize_string(captcha_str)
        captcha_str = captcha_str.replace(" ","_")
        print("Got hCaptcha string:",captcha_str)
        return captcha_str
    
    def get_images(self):
        self.focus_on_frame(2)

        images = []
        print("Trying to get images")
        for i in range(9):
            try:
                print(1)
                img_url = WebDriverWait(self.wd, self.timeout).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div/div[2]/div["+str(i+1)+"]/div[2]/div")))
                print(img_url)
                img_url = img_url.get_attribute("style")
                print(img_url)
                img_url = img_url.split("url(\"")[1]
                print(img_url)
                img_url = img_url.split("\") ")[0]
            except:
                print("Cannot find Image",i+1)
            img_url = urljoin(self.website_url, img_url)
            img_content = requests.get(img_url, stream=True).content
            img = np.array(Image.open(BytesIO(img_content)))
            if img.shape != (160,160,3):
                img = resize(img, (160,160))
            else:
                img = img / 255

            images.append(img)
        images = np.array(images)
        print("Got Captcha Images")
        return images
    
    def click_correct_images(self, predictions):
        self.focus_on_frame(2)

        corr = (predictions > 0.5)
        for i in range(9):
            if corr[i]:
                try:
                    print("Trying to click image", i+1)
                    WebDriverWait(self.wd, self.timeout).until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/div[2]/div["+str(i+1)+"]"))).click()
                    print("Clicked Image",i+1)
                except:
                    print("Cannot find Image",i+1)
                time.sleep(0.5)
        time.sleep(2.0)
        
        print("Trying to click next")
        WebDriverWait(self.wd, self.timeout).until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'button-submit')]"))).click()
        print("Clicked next")
        time.sleep(0.2)
        
        
    def click_refresh(self):
        print("Trying to refresh")
        try:
            WebDriverWait(self.wd, self.timeout).until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'refresh-off')]//*[name()='svg']"))).click()
        except:
            WebDriverWait(self.wd, self.timeout).until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'refresh-on')]//*[name()='svg']"))).click()
        print("Clicked \"refresh\" button")
        time.sleep(0.2)

    def get_verification_status(self):
        self.focus_on_frame(1)

        check_div = WebDriverWait(self.wd, self.timeout).until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'check')]")))
        print(check_div.value_of_css_property("display"))
        if check_div.value_of_css_property("display") == "block":
            return True
        return False