import logging
import time
import traceback
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

from app.config import (AWX_URLS,
                        AWX_INVENTORY_IDX,
                        AWX_HOST_FILTER,
                        CHROME_OPTION,
                        )
from app.errors import AWXLoginFailException

logging.basicConfig()


class AnsibleCrawler:
    def __init__(self, app_name: str, profile: str, project: str):
        self.app_name = app_name
        self.profile = profile
        self.project = project

        # profile 값만 한번 체크

        # profile 값에 따라 AWX 서버 정보 변경
        self.target_url = AWX_URLS[profile]
        self.inventory_index = AWX_INVENTORY_IDX[profile]
        self.host_filter = AWX_HOST_FILTER[profile]

        chrome_options = webdriver.ChromeOptions()

        for item in CHROME_OPTION:
            chrome_options.add_argument(item)

        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                                       options=chrome_options)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers = self.headers

        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.logger.info(f'crawler init (URL: {self.app_name}, profile: {self.profile})')

    def _awx_login(self):
        """
        Private function _
        @ AWX login process
        """
        awx_id = 'jenkins'
        awx_pw = 'dlswmd_1'
        id_tag = self.driver.find_elements(By.ID, 'pf-login-username-id')
        pw_tag = self.driver.find_elements(By.ID, 'pf-login-password-id')
        login_btn = self.driver.find_elements(By.CLASS_NAME, 'pf-c-button')

        id_tag[0].send_keys(awx_id)
        pw_tag[0].send_keys(awx_pw)
        login_btn[0].click()

        # Wait loading time
        time.sleep(1)

        # Login page에는 없는 css class를 이용해서 예외 처리
        check_tag = self.driver.find_elements(By.CLASS_NAME, "pf-c-page__main")
        if not check_tag:
            raise AWXLoginFailException

        self.driver.get(self.target_url + '/#/inventories/inventory/' + str(self.inventory_index) + '/sources/add')

    def make_inventory(self):
        """
        wemakeprice ansible inventory making
        :return: Boolean
        """
        ret_inventory = True

        try:
            print(f'Login process')
            self._awx_login()

            # Move to inventory page
            # index 2 is Dev-AWX inventory index
            # self.driver.get(self.target_url + '/#/inventories/inventory/2/sources/add')
            self.driver.implicitly_wait(1)
            input_list = self.driver.find_elements(By.CLASS_NAME, 'pf-c-form-control')

            tag_input_name = input_list[0]
            tag_input_name.send_keys(self.app_name)

            # Source 'SCM' 선택
            dropdown_src = Select(input_list[2])
            dropdown_src.select_by_value('scm')
            self.driver.implicitly_wait(1)

            btn_project = self.driver.find_elements(By.ID, 'project')
            btn_project[0].click()

            # select project input에 awx_project 이름 넣기, Search to project Name!
            project_wrapper = self.driver.find_elements(By.CLASS_NAME, 'pf-m-filter-group')

            project_wrapper_input = project_wrapper[0].find_element(By.CSS_SELECTOR, "input[class='pf-c-form-control']")
            project_wrapper_input.send_keys(self.project)
            # select project 버튼 클릭
            project_wrapper_btn = project_wrapper[0].find_elements(By.CSS_SELECTOR, "button[aria-label='Search submit button']")
            project_wrapper_btn[0].click()

            time.sleep(1)

            radio_projects = self.driver.find_elements(By.CLASS_NAME, 'pf-c-data-list__item-content')
            radio_projects[0].click()
            btn_select = self.driver.find_elements(By.CLASS_NAME, 'pf-m-primary')
            btn_select = btn_select[2]
            btn_select.click()

            '''
            Select TAG의 값을 입맛에 맞게 수정하는 과정 진행
            inventory/dev/host를 가지고 오지 못하는 경우도 있음..
            무조건 가장 첫번째 항복을 선택하도록
            '''
            source_id = self.driver.find_element(By.ID, 'source_path')
            # 파싱 범위 제한, 항상 존재할 수 있는 마지막 항목을 수정
            option_in_select = source_id.find_element(By.CSS_SELECTOR, "option[value='/ (project root)']")

            '''
            js로 속성, 텍스트 수정하는 로직
            AWX 18.* 문제로 인한 대응 방안
            '''
            self.driver.execute_script(
                f"arguments[0].setAttribute('value', 'inventories/{self.app_name}/hosts')",
                option_in_select)

            self.driver.execute_script(
                f"arguments[0].textContent = 'inventories/{self.app_name}/hosts';",
                option_in_select)

            dropdown_host = Select(self.driver.find_element(By.ID, 'source_path'))
            dropdown_host.select_by_value(f'inventories/{self.app_name}/hosts')

            # Overwrite option check process
            checkbox_options = self.driver.find_elements(By.CLASS_NAME, 'pf-c-check__input')
            opt_overwrite = checkbox_options[0]
            opt_overwrite_vars = checkbox_options[1]
            opt_overwrite.click()
            opt_overwrite_vars.click()

            # input host filter value
            input_host_filter = self.driver.find_element(By.ID, "host-filter")
            input_host_filter.send_keys(self.host_filter)

            # save button click
            btn_select = self.driver.find_elements(By.CLASS_NAME, 'pf-m-primary')
            btn_select = btn_select[1]
            btn_select.click()

            # Sleep for page loading time
            time.sleep(1)
            btns_sync = self.driver.find_elements(By.CLASS_NAME, "pf-m-secondary")

            # sync button click
            btn_sync = btns_sync[1]
            btn_sync.click()

        except AWXLoginFailException:
            logging.error(AWXLoginFailException, exc_info=True)
            ret_inventory = False

        except Exception as e:
            traceback.print_exc(e)
            print(f"Error: {e}")
            ret_inventory = False

        finally:
            self.driver.quit()
            print('Quit crawling')
            return ret_inventory


if __name__ == "__main__":
    crawler = AnsibleCrawler("nd-sre-api", "dev", "develop")
    crawler.driver.get(crawler.target_url)
    time.sleep(1)
    ret = crawler.make_inventory()