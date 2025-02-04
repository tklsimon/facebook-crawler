import fasttext
import logging
import time
import os
import re
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

import utils

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


class FacebookCrawler:
    def __init__(self):
        """
        Initializes the FacebookCrawler with a WebDriver instance and basic settings.
        """
        self.driver = self.__setup_webdriver()
        self.facebook_url = 'https://www.facebook.com/'
        self.other_lang_list = ['xxx', 'yyy']
        self.other_lang_ratio_thrhld = 0.5
        # Login to Facebook
        self.__try_login()

    @staticmethod
    def __setup_webdriver() -> webdriver:
        """
        Sets up the Selenium WebDriver with the required options.
        :return:
            WebDriver instance
        """
        try:
            options = Options()
            options.add_argument('--disable-notifications')
            options.add_argument('--disable-infobars')
            options.add_argument('--mute-audio')
            options.add_argument('--start-maximized')
            # options.add_argument('--headless')
            
            web_driver = webdriver.Chrome(options=options, service=Service(ChromeDriverManager().install()))
            return web_driver
        except Exception as e:
            logging.error(e)
            raise
    
    @staticmethod
    def __get_email_and_password() -> tuple[str, str]:
        """
        Obtain login email and passwoord of the Facebook Account.
        :return:
            login_email: login email of the Facebook Account
            Please: passwoord of the Facebook Account
        """
        # Obtain login email and passwoord from environment variables
        login_email = os.getenv('FB_EMAIL')
        password = os.getenv('FB_PASSWORD')
        # Ask user to enter email and password if one of them is missing
        if not login_email or not password:
            login_email = input('Please enter your email address:')
            password = input('Please enter your password:')
        return login_email, password

    @staticmethod
    def __clean_url(url: str) -> str:
        """
        Cleans and normalizes the Facebook page url.
        :param:
            url: Raw Facebook page URL
        :return:
            Cleaned and normalized URL
        """
        if 'profile.php' in url:
            url = 'https://www.facebook.com/' + \
                (re.search('(?<=id=)([0-9]*)', url)).group(1)
        if '&id=' in url:
            url = 'https://www.facebook.com/' + \
                (re.search('(?<=&id=)([0-9]*)', url)).group(1)
        if '?id=' in url:
            url = 'https://www.facebook.com/' + \
                (re.search('(?<=\?id=)([0-9]*)', url)).group(1)
        if 'comment_id=' in url:
            url = 'https://www.facebook.com/' + \
                (re.search('(?<=www.facebook.com/)([^/]*)', url)).group(1)

        url = re.sub('/p/', '/', url)
        url = re.sub('/pages/', '/', url)
        url = re.sub('facebook.com/category\/(.*?)\/', 'facebook.com/', url)
        url = re.sub('/posts/', '/', url)
        url = re.sub('\/photos/(.*)', '', url)
        url = re.sub('\/public/', '/', url)
        url = re.sub('\/videos/(.*)', '', url)
        url = re.sub('(\?)(.*)', '', url)
        url = re.sub('//pages.', '//www.', url)

        if '/people/' in url or \
            '/commerce/products/' in url or \
            '/groups/' in url or \
            '/hashtag/' in url or \
            'query=' in url:
            return url

        try:
            url = 'https://www.facebook.com/' + \
                (re.search('(?<=www.facebook.com/)([^/]*)', url)).group(1)
        except (AttributeError, TypeError):
            url = None
            pass
        
        return url
    
    @staticmethod
    def __redirect_to_about(url: str) -> str:
        """
        Obtain the "About" page URL.
        :param:
            url: Facebook page url
        :return:
            URL for the About page
        """
        if url[-1] != '/':
            url += '/'
        return url + 'about'

    @staticmethod
    def __redirect_to_transparency(url: str) -> str:
        """
        Obtain the "Page Transparency" page URL.
        :param:
            url: Facebook page url
        :return:
            URL for the Page Transparency page
        """
        if url[-1] != '/':
            url += '/'
        return url + 'about_profile_transparency'
    
    @staticmethod
    def __get_target_line(info_text: str, header: str) -> str:
        """
        Obtain the previous line of the header (escape character is \n).
        :params:
            info_text: Text with required information and header
            header: Name of the header
        :return:
            The line before the header 
        """
        # Split the text into lines
        lines = info_text.split('\n')
        # Find the index of the header
        for i in range(1, len(lines)):
            if lines[i] == header:
                # Return the line before the keyword
                return lines[i-1]
        # Return N/A if no match found
        return 'N/A'
    
    @staticmethod
    def __get_transparency_sections(info_text: str) -> dict:
        """
        Obtain the transparenct sections from the transparency text.
        :param:
            info_text: Text of transparency information
        :return:
            Dictionary of transparency sections
        """
        # Split the text based on headers
        info_line_list = info_text.split('\n')
        
        section_dict = {}
        current_header = None
        # Iterate through the list
        for info_line in info_line_list:
            info_line = info_line.strip()
            if re.match(r'(Page information for [^\n]+' + '|' + \
                          'Organisations that manage this Page' + '|' + \
                          'History' + '|' + \
                          'People who manage this Page' + '|' + \
                          'Ads from this Page)',
                        info_line):
                # If the line matches a header, initialize a section for this header
                if info_line.startswith('Page information'):
                    current_header = 'Page information'
                else:
                    current_header = info_line
                section_dict[current_header] = ''
            elif current_header:
                # Append content to the current header's section if it's not empty
                if section_dict[current_header]:  
                    section_dict[current_header] += '\n'
                section_dict[current_header] += info_line
        
        return {key: section_dict.get(key, 'N/A') \
                    for key \
                    in ['Page information',
                        'Organisations that manage this Page',
                        'History',
                        'People who manage this Page',
                        'Ads from this Page']}
    
    @staticmethod
    def __get_create_date(history_text: str) -> str:
        """
        Obtain create date from history section of transparency.
        :param:
            history_text: Text of history section in transparency
        :return:
            Create date with data type string and format %Y%m%d
        """
        # Split the text into lines
        history_text = history_text.replace('–', '-')
        history_line_list = history_text.split('\n')
        # Get create date
        for index, value in enumerate(history_line_list):
            if value.startswith("Created - "):
                return utils.convert_date_format(history_line_list[index+1], '%Y%m%d')
    
    @staticmethod
    def __get_last_change_name_date(history_text: str) -> str:
        """
        Obtain the last change name date from history section of transparency.
        :param:
            history_text: Text of history section in transparency
        :return:
            The last change name date with data type string and format %Y%m%d.
            Return N/A if there is no change name history
        """
        # Split the text into lines
        history_line_list = history_text.split('\n')
        # Identify the last change name date
        if history_line_list[0].startswith('Changed name to '):
            return utils.convert_date_format(history_line_list[1], '%Y%m%d')
        else:
            # Return N/A if there is no change name history
            return 'N/A'

    @staticmethod
    def __get_historical_name(history_text: str) -> str:
        """
        Obtain all historical name from history section of transparency. 
        :param:
            history_text: Text of history section in transparency
        :return:
            All historical name of the page
        """
        # Split the text into lines
        history_text = history_text.replace('–', '-')
        history_line_list = history_text.split('\n')
        
        page_name_list = []
        # Iterate over the lines
        for history_line in history_line_list:
            # Check if the line contains a date
            if (history_line.startswith('Created - ')) or \
                (history_line.startswith('Changed name to ')):
                # Remove the specified text
                history_line = re.sub(r'^Created - ', '', history_line)
                history_line = re.sub(r'^Changed name to ', '', history_line)
                history_line = history_line.strip()
                page_name_list.append(history_line)
        return '\n'.join(page_name_list)

    @staticmethod
    def __get_hk_admin_ratio(admin_text: str) -> float:
        """
        Obtain the ratio of Hong Kong admin.
        :param:
            history_text: Text of history section in transparency
        :return:
            Ratio of Hong Kong admin in float, i.e. 0.1 for 10%
        """
        admin_text = re.sub(
            r'^Primary country/region location for people who manage this Page includes:\n',
            '',
            admin_text)
        
        # Regular expression to find countries and their counts
        matches = re.findall(r'(\w[\w\s]+) \((\d+)\)', admin_text)
        
        # Populate the dictionary with country counts
        country_count_dict = dict()
        for country, count in matches:
            country_count_dict[country] = int(count)

        # Ratio for output
        if country_count_dict == dict():
            return None
        elif 'Hong Kong' in country_count_dict.keys():
            return round((country_count_dict['Hong Kong'] / sum(country_count_dict.values())) * 100, 2)
        else:
            return 0.0
    
    @staticmethod
    def __get_advertisement_indicator(advertisement_text: str) -> str:
        """
        Obtain the indicator of advertisement.
        :param:
            admin_text: Text of advertisement section in transparency
        :return:
            'Y' if the page is running ads. Otherwise, 'N'
        """
        if advertisement_text.startswith('This Page is currently running ads.'):
            return 'Y'
        elif advertisement_text.startswith('This Page is not currently running ads.'):
            return 'N'
        else:
            logging.error('Unexpected value received in advertisement text!!!')
            raise
    
    def __get_login_status(self) -> bool:
        """
        Check Facebook login status.
        :return:
            True if logged in. Otherwise, False
        """
        # Navigate to Facebook if not in Facebook website
        current_url = self.driver.current_url
        if not current_url.startswith(self.facebook_url):
            self.driver.get(self.facebook_url)

        # Check if "Log in" exists
        body_text = self.driver.find_element(By.TAG_NAME, 'body').text
        if 'Log in' in body_text or \
            (('human' in body_text) & ('login attempt' in body_text)):
            return False
        else:
            return True
    
    def __login(self, login_email, password) -> None:
        """
        Try to login for 1 time with the given email and password
        :params:
            login_email: Email of the Facebook account
            password: Password of the Facebook account
        """
        email_input = self.driver.find_element(By.ID, 'email')
        email_input.send_keys(login_email)
        
        password_input = self.driver.find_element(By.ID, 'pass')
        password_input.send_keys(password)
        
        login_button = self.driver.find_element(By.NAME, 'login')
        login_button.click()
    
    def __try_login(self, max_attempt_nbr=5) -> None:
        """
        Try to login for few times.
        :param:
            max_attempt_nbr: The maximum number of login attempt
        """
        # Check if logged in already
        logging.info('Trying to login to Facebook...')
        login_status = self.__get_login_status()
        if login_status:
            logging.info('Already logged in. No action is needed.')
            return

        login_email, password = self.__get_email_and_password()
        
        # Try to login
        self.driver.get(self.facebook_url)
        for i in range(1, max_attempt_nbr+1):
            self.__login(login_email, password)
            if self.__get_login_status():
                logging.info('Successfully logged in.')
                return
            
            if i == max_attempt_nbr:
                logging.error(f'Cannot login within {max_attempt_nbr} attempts!!!')
            
            WebDriverWait(self.driver, 5) \
                .until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            body_text = self.driver.find_element(By.TAG_NAME, 'body').text
            # Check if Captcha is required
            if ('human' in body_text) & ('login attempt' in body_text):
                # Switch to the new window
                logging.info('CAPTCHA is needed.')
                logging.info('Will try to login in a new window.')
                self.driver.execute_script(f"window.open('{self.facebook_url}');")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                time.sleep(5)
            # Check if password is incorrect
            elif (('password' in body_text) & ('incorrect' in body_text)) or \
                    (('密碼' in body_text) & ('不正確' in body_text)):
                logging.info('Password is incorrect. 密碼不正確.')
                logging.info('Please enter your email and password again.')
                login_email = input('Please enter your email address:')
                password = input('Please enter your password:')
                not_me_button = self.driver.find_element(By.ID, 'not_me_link')
                not_me_button.click()
    
    def __click_button(self, label: str) -> None:
        """
        Click the button with the required aria-label
        :param:
            label: aria-label of the button.
        """
        button = WebDriverWait(self.driver, 3) \
            .until(EC.presence_of_element_located((By.XPATH, f"//div[@aria-label='{label}']")))
        button.click()
    
    def __try_click_button(self, label: str) -> None:
        """
        Try to click the button with the required aria-label. Ignore if error occurs.
        :param:
            label: aria-label of the button.
        """
        try:
            self.__click_button(label)
        except:
            pass
    
    def __get_page_name(self, clean_url: str) -> str:
        """
        Obtain page name from the Facebook page.
        :param:
            clean_url: Cleaned URL of the Facebook page
        :return:
            Name of the Facebook page
        """
        about_url = self.__redirect_to_about(clean_url)
        self.driver.get(about_url)
        
        head = self.driver \
            .find_element(By.TAG_NAME, value='head')
        title = head \
            .find_element(By.TAG_NAME, value='title') \
            .get_attribute('innerHTML')
        
        page_name = re.sub(r'\(\d+\)\s*', '', title)
        page_name = page_name.replace(' | Facebook', '')
        if page_name:
            return page_name
        else:
            return None
    
    def __scroll_down_and_check_bottom(self, last_height) -> str | int:
        """
        Scroll down the page and return the new hieght or 'buttom' if bottom is reached.
        :param:
            last_hieght: Last height of the page before scrolling down
        :return:
            New hieght of the page after scrolling down, or 'buttom' if bottom is reached
        """
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.75);")
        time.sleep(2)
        new_height = self.driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            return 'bottom'
        return new_height
    
    def __search_pages(self, keywords: str, scroll_down_nbr: int=3) -> list[tuple]:
        """
        Obtain page names and URLs of Facebook pages by searching with keywords.
        :param:
            keywords: Keywords to search for Facebook pages
            scroll_down_nbr: Maximum number of times to scroll down to load more results
        :return:
            A list of tuples containing the page names and URLs of the searched results
        """
        # Navigate to the Facebook Home page
        self.driver.get(self.facebook_url)
        
        # Locate the search box and enter the keywords
        logging.info(f'Finding Facebook pages using the keywords "{keywords}"...')
        search_box = self.driver \
            .find_element(By.CSS_SELECTOR, '[aria-label="Search Facebook"]')
        search_box.send_keys(keywords)
        # Submit the search (press Enter)
        search_box.send_keys(u'\ue007')
        time.sleep(3)
        
        # Check the search results for Facebook Pages
        pages_button = self.driver \
            .find_element(By.XPATH, '//span[text()="Pages"]')
        pages_button.click()
        
        WebDriverWait(self.driver, 5) \
            .until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[role="presentation"]')))
        
        # Scroll down to load more results if needed
        if scroll_down_nbr > 0:
            scroll_height = self.driver.execute_script("return document.body.scrollHeight")
            for i in range(scroll_down_nbr):
                logging.info(f'Scrolling down ({i+1}/{scroll_down_nbr})...')
                scroll_height = self.__scroll_down_and_check_bottom(scroll_height)
                if scroll_height == 'bottom':
                    logging.info('Reached bottom. Stop scrolling.')
                    break

        # Identify all search results
        results = self.driver \
            .find_elements(By.CSS_SELECTOR, 'a[role="presentation"]')
        
        # Extract result page names and their URLs 
        page_list = []
        for result in results:
            page_name = result.text
            page_url = result.get_attribute('href')
            page_list.append((page_name, page_url))
        
        return page_list
    
    def __fetch_about_info(self, clean_url: str) -> str:
        """
        Fetches the information in the About section from the given Facebook page.
        :param:
            clean_url: Cleaned Facebook page URL
        :return:
            Text content from the About section
        """
        logging.info('Fetching about page information...')
        
        # Navigate to the "About" page
        about_url = self.__redirect_to_about(clean_url)
        self.driver.get(about_url)

        try:
            WebDriverWait(self.driver, 5) \
                .until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            web_element = self.driver \
                .find_element(By.CLASS_NAME, value='x1yztbdb') \
                .find_element(By.CLASS_NAME, value='x1iyjqo2')
            return web_element.text
        except NoSuchElementException:
            logging.error('Can NOT find the page web elements!!!')
            raise

    def __fetch_transparency_info(self, clean_url: str) -> str | None:
        """
        Fetches the information in the Page Transparency section from the given Facebook page.
        :param:
            clean_url: Cleaned Facebook page URL
        :return:
            Text content from the Page Transparency section
        """
        logging.info('Fetching transparency page information...')
        
        # Navigate to the "Page Transparency" section
        transparency_url = self.__redirect_to_transparency(clean_url)
        self.driver.get(transparency_url)
        
        # Click the "See All" button
        self.__click_button('See All')

        # Click the 'See xx More' button in the History part if it exists
        try:
            WebDriverWait(self.driver, 3) \
                .until(EC.visibility_of_element_located(
                    (By.XPATH,
                     '//div[starts-with(@aria-label, "See ") and \
                     contains(@aria-label, " More")]')))
            
            button = self.driver \
                .find_element(By.XPATH,
                              '//div[starts-with(@aria-label, "See ") and \
                              contains(@aria-label, " More")]')
            
            self.__click_button(button.get_attribute('aria-label'))
        except:
            pass

        # Try to obtain the text from the Page Transparency section
        for i in range(10):
            try:
                web_element = self.driver \
                    .find_element(By.CLASS_NAME, value='xb57i2i')
                if web_element.text != '':
                    return web_element.text
            except:
                time.sleep(0.5)
        logging.error('Can NOT find page transparency info!!!')
        raise
    
    def __get_like_dialog_text(self, next_like_element: WebElement) -> str:
        """
        Extracts the text content of the like dialog.
        :param:
            next_like_element: Next like WebElement to be clicked
        :return:
            Text content of the like dialog
        """
        # Scroll the button into view and center it in the viewport
        self.driver.execute_script("""
            var element = arguments[0];
            var rect = element.getBoundingClientRect();
            var centerY = window.innerHeight / 2;
            var elementY = rect.top + window.scrollY + (rect.height / 2);
            window.scrollTo(0, elementY - centerY);
        """, next_like_element)
        time.sleep(1)
        next_like_element.click()
        time.sleep(0.5)
        dialog_element = self.driver.find_element(By.XPATH, '//div[@role="dialog"]')
        return dialog_element.text
    
    def __get_people_liked_and_language(self, dialog_text: str, lang_model) -> list[tuple]:
        """
        Extracts user names and detected languages from the like dialog text.
        :param:
            dialog_text: Text content of the dialog
        :return:
            List of tuples containing user names and their detected languages
        """
        dialog_line_list = dialog_text.split('\n')
        
        name_lang_list = []
        for dialog_line in dialog_line_list:
            if not (re.match(r'^\d', dialog_line) or \
                    dialog_line in ["All", "More", "Add friend", "Follow"]):
                prediction = lang_model.predict(dialog_line)
                lang_code = prediction[0][0].replace("__label__", "")
                name_lang_list.append((dialog_line, lang_code))
        return name_lang_list
    
    def __get_language_ratios(self, name_lang_list: list[tuple]) -> dict:
        """
        Calculates the ratio of each language in the provided list of user names and languages.
        :param:
            name_lang_list: List of tuples containing user names and their languages
        :return:
            Dictionary mapping language codes to their ratios
        """
        lang_counts = {}
        for _, lang in name_lang_list:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        total_count = sum(lang_counts.values())
        return {lang: count / total_count for lang, count in lang_counts.items()}
    
    def __check_other_lang_like(self, clean_url: str, scroll_down_nbr: int=3) -> dict:
        """
        Checks posts of a Facebook page for likes from users in other languages.
        :params:
            clean_url: Cleaned Facebook page URL to be crawled
            scroll_down_nbr: Maximum number of times to scroll down the page to load more posts
        :return:
            Dictionary containing post text, liked names with their languages, and the other language ratio.
        """
        # Load the pre-trained language detection model
        lang_model = fasttext.load_model("lid.176.bin")
        
        self.driver.get(clean_url)
        time.sleep(1)
        
        logging.info('Crawling posts...')
        scroll_height = self.driver.execute_script("return document.body.scrollHeight")
        for i in range(scroll_down_nbr+1):
            # Scroll down
            if i > 0:
                logging.info(f'Scrolling down ({i}/{scroll_down_nbr})...')
                scroll_height = self.__scroll_down_and_check_bottom(scroll_height)
                if scroll_height == 'bottom':
                    logging.info('Reached bottom. Stop scrolling.')
                    break
            
            try:
                WebDriverWait(self.driver, 5) \
                    .until(EC.presence_of_element_located((By.XPATH, '//div[@data-ad-rendering-role="story_message"]')))
                post_list = self.driver.find_elements(By.XPATH, '//div[@data-ad-rendering-role="story_message"]')
                
                for post in post_list:
                    try:
                        next_like_button = post.find_element(By.XPATH, './following::div[contains(@aria-label, "Like:")][1]')
                        dialog_text = self.__get_like_dialog_text(next_like_button)
                        name_lang_list = self.__get_people_liked_and_language(dialog_text, lang_model)
                        
                        lang_ratio_dict = self.__get_language_ratios(name_lang_list)
                        other_lang_ratio = sum(lang_ratio_dict[key] for key in self.other_lang_list if key in lang_ratio_dict)
                        if other_lang_ratio >= self.other_lang_ratio_thrhld:
                            logging.info('Found a required post. Stop crawling posts.')
                            return {'post_text': post.text,
                                    'liked_name': name_lang_list,
                                    'other_lang_ratio': other_lang_ratio}
                    except:
                        pass
                    finally:
                        self.__try_click_button('Close')
            except:
                pass
        return {'post_text': "N/A",
                'liked_name': "N/A",
                'other_lang_ratio': 0}
    
    def crawl_page(self, url: str) -> dict:
        """
        Crawl the information in the About and Page Transparency sections from the given Facebook page.
        :param:
            url: A Facebook page URL
        :return:
            Dictionary containing required information from the About and Page Transparency sections
        """
        clean_url = self.__clean_url(url)
        page_name = self.__get_page_name(clean_url)
        logging.info(f"Crawling {page_name}...")
        
        # About and transparency information
        about_info_text = self.__fetch_about_info(clean_url)
        transparency_info_text = self.__fetch_transparency_info(clean_url)
        # Sections in transparency
        transparency_sections = self.__get_transparency_sections(transparency_info_text)
        transparency_history = transparency_sections['History']
        transparency_admin = transparency_sections['People who manage this Page']
        transparency_ads = transparency_sections['Ads from this Page']
        # Extract information
        phone = self.__get_target_line(about_info_text, 'Mobile')
        address = self.__get_target_line(about_info_text, 'Address')
        website = self.__get_target_line(about_info_text, 'Website')
        create_date = self.__get_create_date(transparency_history)
        last_change_name_date = self.__get_last_change_name_date(transparency_history)
        historical_name = self.__get_historical_name(transparency_history)
        hk_admin_ratio = self.__get_hk_admin_ratio(transparency_admin)
        advertisement_indicator = self.__get_advertisement_indicator(transparency_ads)
        # Other language like 
        other_lang_like = self.__check_other_lang_like(clean_url)
        other_lang_post_text = other_lang_like['post_text']
        other_lang_liked_name = other_lang_like['liked_name']
        other_lang_ratio = other_lang_like['other_lang_ratio']
        
        # Result Dictionary
        return {'page_name': page_name,
                'url': url,
                'about_info_text': about_info_text,
                'transparency_info_text': transparency_info_text,
                'transparency_history': transparency_history,
                'transparency_admin': transparency_admin,
                'transparency_ads': transparency_ads,
                'other_lang_post_text': other_lang_post_text,
                'other_lang_liked_name': other_lang_liked_name,
                'phone': phone,
                'address': address,
                'website': website,
                'create_date': create_date,
                'last_change_name_date': last_change_name_date,
                'historical_name': historical_name,
                'hk_admin_ratio': hk_admin_ratio,
                'advertisement_indicator': advertisement_indicator,
                'other_lang_ratio': other_lang_ratio}
    
    def crawl_pages(self, urls: list[str]) -> dict:
        """
        Crawl the information in the About and Page Transparency sections from the given list of Facebook pages.
        :param:
            urls: List of Facebook page URLs
        :return:
            Dictionary containing required information from the About and Page Transparency sections for each URL
        """
        result_dict = {}
        for index, url in enumerate(urls, start=1):
            logging.info(f'{index}. URL: {url}')
            result_dict[url] = self.crawl_page(url)
        logging.info('Crawling completed.')
        return result_dict
    
    def search_and_crawl_pages(self,
                               keywords: str,
                               search_scroll_down_nbr: int=3,
                               max_page_nbr: int=None) -> dict:
        """
        Crawl Facebook pages which are obtained by searching with keywords.
        :param:
            keywords: Keywords to search for Facebook pages
            scroll_down_nbr: Number of times to scroll down to load more results
            max_page_nbr: Maximum number of pages to crawl. If not specified, all found pages will be crawled.
        :return:
            Dictionary containing the information from the About and Page Transparency sections for each URL
        """
        search_result = self.__search_pages(keywords, search_scroll_down_nbr)
        result_url_list = [result[1] for result in search_result]
        result_url_cnt = len(result_url_list)
        logging.info(f'Obtained {result_url_cnt} URLs from the search result.')
        if max_page_nbr and (result_url_cnt > max_page_nbr):
            logging.info(f'Will only crwal the top {max_page_nbr} pages.')
            return self.crawl_pages(result_url_list[:max_page_nbr])
        else:
            return self.crawl_pages(result_url_list)

    def close(self) -> None:
        """
        Close the WebDriver instance.
        """
        self.driver.quit()
