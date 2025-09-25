import os
import sys
import threading
import time
from typing import Any, Dict, Optional, List, Tuple
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
import pyautogui
import random
import glob
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from module.bot.gemini_post_fb import gemini_post_generate

ADSPOWER_API_BASE = "http://local.adspower.net:50325/api/v1"


def start_adspower_profile(user_id: str) -> Dict[str, Any]:

	url = f"{ADSPOWER_API_BASE}/browser/start"
	resp = requests.get(url, params={"user_id": user_id}, timeout=30)
	resp.raise_for_status()
	data = resp.json()
	if data.get("code") != 0:
		raise RuntimeError(f"AdsPower start failed: {data}")
	return data["data"]


def wait_for_debug_port(host: str, port: str, timeout_seconds: int = 15) -> None:

	deadline = time.time() + timeout_seconds
	# Simple polling against /json/version endpoint (DevTools) to ensure it's ready
	endpoint = f"http://{host}:{port}/json/version"
	last_err: Optional[Exception] = None
	while time.time() < deadline:
		try:
			resp = requests.get(endpoint, timeout=3)
			if resp.ok:
				return
		except Exception as exc:  # noqa: BLE001 - best-effort wait loop
			last_err = exc
		time.sleep(0.5)
	if last_err:
		raise RuntimeError(f"DevTools on {host}:{port} not ready") from last_err
	raise RuntimeError(f"DevTools on {host}:{port} not ready (unknown error)")


def attach_selenium_to_adspower(debug_port: str, chromedriver_path: str) -> webdriver.Chrome:

	options = ChromeOptions()
	options.add_experimental_option("debuggerAddress", f"127.0.0.1:{debug_port}")
	service = ChromeService(executable_path=chromedriver_path)
	# Create a WebDriver that attaches to the already-running Chrome via debuggerAddress
	driver = webdriver.Chrome(service=service, options=options)
	return driver


def post_run(user_id: Optional[str] = None, *, context: str = "", api_key: str = "", model: str = "", schedule: Optional[List[Tuple[str, str]]] = None, settings: Optional[Dict[str, Any]] = None, stop_event: Optional[threading.Event] = None) -> None:
    # Prioritize explicitly passed user_id; fallback to environment variable
    if not user_id:
        user_id = os.getenv("ADSPOWER_USER_ID", "k1571o14")
    profile = start_adspower_profile(user_id)

    debug_port = str(profile.get("debug_port"))
    chromedriver_path = str(profile.get("webdriver"))
    if not debug_port or not chromedriver_path:
        raise RuntimeError(f"Missing debug_port/webdriver from AdsPower response: {profile}")

	# Ensure DevTools endpoint is responding before Selenium attaches
    wait_for_debug_port("127.0.0.1", debug_port, timeout_seconds=20)

    driver = attach_selenium_to_adspower(debug_port, chromedriver_path)
    try:
        original_handle = None
        try:
            original_handle = driver.current_window_handle
        except Exception:
            pass

        # Settings: images per post range and delay range
        settings = settings or {}
        images_min = int(settings.get("imagesMin", 1) or 1)
        images_max = int(settings.get("imagesMax", max(1, images_min)) or images_min)
        if images_max < images_min:
            images_max = images_min
        delay_min = max(0, int(settings.get("delayMin", 0) or 0))
        delay_max = max(delay_min, int(settings.get("delayMax", delay_min) or delay_min))
        driver.switch_to.new_window('tab')

        for s in schedule:
            if stop_event and stop_event.is_set():
                print("Stop requested. Exiting loop.")
                break
            
            driver.get("https://business.facebook.com/latest/home")
            # click //div[@role='button' and contains(., 'Create post')]
            driver.find_element(By.XPATH, "//div[@role='button' and contains(., 'Create post')]").click()
            time.sleep(5)

            # Resolve images directory from project root: <project>/temp/images_random
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            images_dir = os.path.join(project_root, "temp", "images_random")
            patterns = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.bmp"]
            image_files = []
            for pattern in patterns:
                image_files.extend(glob.glob(os.path.join(images_dir, pattern)))
            if not image_files:
                raise RuntimeError(f"No image files found in: {images_dir}")
            # Choose random number of images per post within range
            num_images = random.randint(images_min, images_max)
            chosen = random.sample(image_files, k=min(num_images, len(image_files)))
            for idx, selected_image in enumerate(chosen, start=1):
                if stop_event and stop_event.is_set():
                    print("Stop requested during image selection.")
                    break
                driver.find_element(By.XPATH, "//div[@aria-label='Select adding photos.']").click()
                time.sleep(1)
                print(f"Add image {idx}/{len(chosen)} => {selected_image}")
                pyautogui.write(selected_image)
                pyautogui.press("enter")
                time.sleep(0.4)
                time.sleep(0.4)


            # Tìm ô soạn thảo văn bản (contenteditable)
            text_editor = driver.find_element(By.CSS_SELECTOR, 'div[contenteditable="true"][role="combobox"]')

            # Click để focus
            text_editor.click()

            # Xóa nội dung cũ (nếu cần)
            text_editor.clear()  # ⚠️ Có thể không hoạt động với contenteditable

            # Gửi văn bản mới
            print(user_id, context, api_key, model, schedule)

            content = gemini_post_generate(content=context, apikey=api_key, model=model)
            
            text_to_post = content.strip() or "TEST 01"
            text_editor.send_keys(text_to_post)

            # Nếu có schedule, chọn thời gian đăng theo phần tử đầu tiên

            if schedule:
                first = s
                try:
                    date_str, time_hm = first
                    # Hỗ trợ 'YYYY-MM-DD' hoặc 'M/D/YYYY' (ưu tiên M/D/YYYY như UI mới)
                    if '-' in date_str:
                        yyyy, mm, dd = date_str.split('-')
                        mmddyyyy = f"{int(mm)}/{int(dd)}/{yyyy}"
                    else:
                        # assume already M/D/YYYY
                        mmddyyyy = date_str
                    print("schedule..")
                    driver.find_element(By.XPATH, "//input[@aria-label='Set date and time']").click()
                    time.sleep(2)

                    date_input = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '//input[@placeholder="mm/dd/yyyy"]'))
                    )
                    actions = ActionChains(driver)
                    actions.click(date_input).key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
                    actions = ActionChains(driver)

                    
                    actions.send_keys(mmddyyyy).perform()
                    # Tab tới time input (hour field)
                    actions.send_keys(Keys.TAB).perform()
                    # time_hm có dạng "02:00 PM": nhập giờ -> Tab -> phút -> Tab -> 'p'/'a' -> Tab
                    try:
                        raw = (time_hm or "").strip()
                        # Normalize spaces and case
                        parts = raw.upper().split()
                        time_part = parts[0] if parts else ""
                        ampm_part = parts[1] if len(parts) > 1 else ""
                        hour_str, minute_str = (time_part.split(":", 1) + [""])[:2]
                        # Fallbacks
                        hour_str = ("" if hour_str is None else hour_str).strip()
                        minute_str = ("" if minute_str is None else minute_str).strip()
                        if hour_str:
                            hour_str = str(int(hour_str)).zfill(2)
                        if minute_str:
                            minute_str = str(int(minute_str)).zfill(2)

                        # Hour
                        if hour_str:
                            actions.send_keys(hour_str).perform()
                        # Move to minute
                        actions.send_keys(Keys.TAB).perform()
                        # Minute
                        if minute_str:
                            actions.send_keys(minute_str).perform()
                        # Move to AM/PM toggle
                        actions.send_keys(Keys.TAB).perform()
                        # AM/PM by typing initial
                        ampm_initial = 'P' if ampm_part.startswith('P') else ('A' if ampm_part.startswith('A') else '')
                        if ampm_initial:
                            actions.send_keys(ampm_initial.lower()).perform()
                        actions.send_keys(Keys.TAB).perform()
                        time.sleep(2)
                        driver.find_element(By.XPATH, "//div[@role='button' and .//text()='Schedule']").click()

                    except Exception:
                        actions.send_keys(time_hm).perform()
                except Exception:
                    pass
            else:
                time.sleep(2)
                driver.find_element(By.XPATH, "//div[@role='button' and .//text()='Publish']").click()
            time.sleep(3)
            delay_seconds = random.randint(delay_min, delay_max)
            if delay_seconds > 0:
                print(f"Delay next post: {delay_seconds}s")
                # Sleep in small chunks to be responsive to stop
                slept = 0
                while slept < delay_seconds:
                    if stop_event and stop_event.is_set():
                        print("Stop requested during delay.")
                        break
                    chunk = min(1, delay_seconds - slept)
                    time.sleep(chunk)
                    slept += chunk
    except Exception as e:
        print(e)
    finally:
        try:
            driver.quit()
        except Exception:
            pass





