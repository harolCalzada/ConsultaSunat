from selenium import webdriver
from selenium.common.exceptions import *
import contextlib
from PIL import Image
import pyocr
import requests
import bs4
import sys

@contextlib.contextmanager
def browse(driver):
    yield driver
    driver.quit()

def get_subimage(source, loc, size):
    img = Image.open(source)

    left = loc['x']
    top = loc['y']
    right = loc['x'] + size['width']
    bottom = loc['y'] + size['height']

    img = img.crop((left, top, right, bottom))

    return img

def get_text_from_image(image):
    tools = pyocr.get_available_tools()
    if len(tools) == 0:
        print("No OCR tool found")
        exit(1)

    tool = tools[0]

    return tool.image_to_string(image)

def get_captcha_image(driver, frame_elem):
    img_xpath = '//img[@src="captcha?accion=image"]'
    driver.switch_to.frame(frame_elem)
    try:
        driver.save_screenshot('image.png')
        img_elem = driver.find_element_by_xpath(img_xpath)
    except NoSuchElementException as e:
        print(e)
        return ''

    loc = img_elem.location
    size = img_elem.size
    captcha = get_subimage('image.png', loc, size)
    captcha.save('captcha.png')
    driver.switch_to_default_content()

    return captcha

def get_captcha_text(driver, frame_elem):
    captcha = get_captcha_image(driver, frame_elem)
    if not captcha:
        return ''
    return get_text_from_image(captcha)

def save_results(driver, filename):
    result_frame = driver.find_element_by_xpath('//frame[@src="frameResultadoBusqueda.html"]')
    driver.switch_to.frame(result_frame)
    source = driver.page_source
    with open(filename, 'w') as f:
        f.write(source)
    driver.switch_to_default_content()

def parse_results_file(filename):
    with open(filename, 'r') as f:
        text = f.read()
    html = bs4.BeautifulSoup(text, "lxml")
    print(html)
    return None

def get_data_by_ruc(driver, search_frame, ruc, captcha):
    driver.switch_to.frame(search_frame)
    try:
        ruc_input = driver.find_element_by_xpath('//input[@name="search1"]')
        captcha_input = driver.find_element_by_xpath('//input[@name="codigo"]')
        submit_btn = driver.find_element_by_xpath('//input[@value="Buscar"]')
    except NoSuchElementException as e:
        print(e)
        return None

    ruc_input.send_keys(str(ruc))
    captcha_input.send_keys(str(captcha))
    submit_btn.click()
    driver.save_screenshot('image2.png')
    driver.implicitly_wait(10)

    driver.switch_to_default_content()

    save_results(driver, 'frame.xml')

    data = parse_results_file('frame.xml')

    return data

def main():
    if len(sys.argv) != 2:
        print("Usage")
    url_sunat = 'http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias'
    search_frame_xpath = '//frame[@src="frameCriterioBusqueda.jsp"]'

    with browse(webdriver.PhantomJS()) as driver:
        driver.get(url_sunat)
        try:
            search_frame = driver.find_element_by_xpath(search_frame_xpath)
        except NoSuchElementException as e:
            print(e)
            return

        captcha = get_captcha_text(driver, search_frame)
        print("Text in captcha:", captcha)
        if not captcha:
            print("Error reading captcha")
            return
        
        ruc = '20331066703'
        data = None
        try:
            data = get_data_by_ruc(driver, search_frame, ruc, captcha)
        except NoSuchElementException as e:
            print(e)

        print(data)

if __name__ == '__main__':
    main()