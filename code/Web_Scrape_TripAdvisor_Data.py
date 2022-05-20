
import os
import re
import jsonlines
import numpy as np
import pandas as pd
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from argparse import ArgumentParser
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from LocalSettings import chromedriver_path, DataLocation
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException


# arguments
parser = ArgumentParser()
parser.add_argument('-f', '--file', type=str, help='Output file name.')
parser.add_argument('-b', '--begin', type=int, default=0, help='Beginning file index number.')
parser.add_argument('-e', '--end', type=int, help='Number of Pages to parse.')
parser.add_argument('-o', '--overwrite', type=str, help='Pass "a" to append or "w" to overwrite an existing file.')
parser.add_argument('--first_pages', action='store_true')
args = parser.parse_args()

if not args.file:
    raise Exception(
        'Output file name not provided. use -f to specify your file name.')

if not args.overwrite and args.file in os.listdir('Outputs'):
    raise Exception(
        f'{args.file} already exists. use "-o a" to append. use "-o w" to overwrite.')

elif not args.overwrite:
    args.overwrite = 'w'

if not args.end:
    args.end = args.begin+50000

# chrome driver settings
topics_xpath = "//div[@class='XUVJZtom'][@data-test-target='expand-review']"
options = Options()
options.add_argument("--disable-infobars")
options.add_argument('--headless')
browser = webdriver.Chrome(executable_path=chromedriver_path, options=options)


def get_page(webpage: str):
    """ parse webpage """

    soup = BeautifulSoup(webpage, 'lxml')
    return soup


def hotel_name(soup):
    """ get hotel names and address from All hotel pages """

    try:
        return soup.find("h1", id='HEADING').text
    except:
        return None


def hotel_address(soup):
    """ get hotel address """

    try:
        return soup.find('span', {'class': '_3ErVArsu jke2_wbp'}).text
    except:
        return None


def count_reviews(soup):
    """ Hotel Total Number of Reviews """

    try:
        return int(soup.find('span', {'class': '_33O9dg0j'}).text.replace(' reviews', ''))
    except:
        return None


def review_pages(soup):
    """ Find/Create All Review Pages Available (The number of Pages Depends on the Number of Reviews) """

    try:
        all_links = soup.find_all('a', {'class': 'pageNum'})
        hyperlink = []
        for line in all_links:
            AdditionalPagesInfo = {'hyperlink': line['href'],
                                   'pageNum': int(line.text)}
            hyperlink.append(AdditionalPagesInfo)
        available_links = pd.DataFrame(hyperlink)
        page_number_list = available_links.pageNum.tolist()
        ReviewLinks = available_links.hyperlink.tolist()
        if len(page_number_list) > 1:
            if page_number_list[-1] - page_number_list[-2] > 1:
                regex = r"Reviews\-or\d+"
                template_link = available_links.iloc[0, 0]
                # missing_pages_count = page_number_list[-1] - page_number_list[-2]
                for i in range(page_number_list[-2]*5, (page_number_list[-1]-1)*5, 5):
                    ReviewLinks.append(re.sub(regex, f'Reviews-or{i}', template_link))
                return ReviewLinks
            else:
                return ReviewLinks
        else:
            return ReviewLinks
    except:
        return None


# Extract Reviews and the information of the reviewers
def review_box(soup):
    """ Review Box: each page has a maximum of 5 boxes """

    try:
        return soup.find_all('div', {'class': '_2wrUUKlw _3hFEdNs8'})
    except:
        return None


def reviewer_name(box) -> str:
    """ Reviewer Name and Profile """

    try:
        return box.find('a', {'class': 'ui_header_link _1r_My98y'}).text
    except:
        return ""


def reviewer_profile(box) -> str:
    """ link to reviewer profile """

    try:
        return box.find('a', {'class': 'ui_header_link _1r_My98y'})['href']
    except:
        return ""


def review_id(box) -> int:
    """ unique review id """

    try:
        return box.find('div', {'class': 'oETBfkHU'})['data-reviewid']
    except:
        return np.nan


def review_date(box) -> str:
    """ date of the review """

    try:
        return box.find('div', {'class': '_2fxQ4TOx'}).text.replace(reviewer_name(box)+' wrote a review ', '')
    except:
        return ""


def reviewer_location(box):
    """ Location of the Reviewer """

    try:
        return box.find('span', {'class': 'default _3J15flPT small'}).text
    except:
        return ""


def reviewer_contribution(box) -> int:
    """ Reviewers Total Contribution """

    try:
        regex = r'contributions?'
        contributions = box(text=re.compile(regex))[0].parent.text
        return int(re.sub(regex, '', contributions))
    except:
        return np.nan


def review_helpful_votes(box) -> int:
    """ Review Helpful Votes """

    try:
        regex = r'helpful votes?'
        Votes = box(text=re.compile(regex))[0].parent.text
        return int(re.sub(regex, '', Votes))
    except:
        return np.nan


def review_star(box):
    """ Number of Stars provided to hotel by the reviewer """

    try:
        regex = r'ui\_bubble\_rating bubble\_\d+'
        match = re.findall(regex, str(box))[0]
        score = int(re.findall(r'\d+', match)[0])
        return score
    except:
        return np.nan


def review_text(box):
    """ The text of the review """

    try:
        return box.find('q', {'class': 'IRsGHoPm'}).text
    except:
        return None


def date_of_stay(box):
    """ Date of Stay """

    try:
        return box.find('span', {'class': '_34Xs-BQm'}).text.strip().replace('Date of stay: ', '')
    except:
        return None


# Trip Type
def trip_type(box):
    try:
        return box.find('span', {'class': '_2bVY3aT5'}).text.strip().replace('Trip type: ', '')
    except:
        return None


def ratings_detail(box):
    """ Rating Details in the Review """

    Rating_values = {}
    try:
        RatingDetails = box.find_all('div', {'class': '_3ErKuh24 _1OrVnQ-J'})
        for Rating in RatingDetails:
            Rating_values[f'{Rating.text}Score'] = review_star(Rating)
        return Rating_values
    except:
        return Rating_values


def response_details(box):
    """ Response of the Hotel """

    try:
        # ResponseBox = box.find('div', {'class': 'XPYR1502'})
        ResponseInfo = {'ResponderName': box.find('div', {'class': '_204cKjWJ'}).text,
                        'ResponseDate': box.find('div', {'class': '_2lY-Jowi'})['title'],
                        'ResponseText': box.find('span', {'class': 'sT5TMxg3'}).text}
        return ResponseInfo
    except:
        return {'ResponderName': None,
                'ResponseDate': None,
                'ResponseText': None}


def scrape_additional_pages():
    New_Review_linksPD = pd.read_csv('Outputs/Additional_Review_Pages.csv', names=['link'])
    ReviewPageList = New_Review_linksPD.link.tolist()
    ReviewPageList.sort()
    ScrapeList = ReviewPageList[args.begin: args.end]
    with jsonlines.open(f'Outputs/{args.file}', args.overwrite) as destination:
        for link in tqdm(ScrapeList):
            try:
                browser.get(link)
                browser.execute_script("arguments[0].scrollIntoView(false);",
                                       browser.find_element_by_xpath(topics_xpath))
                WebDriverWait(browser, 10).until(
                    expected_conditions.visibility_of_any_elements_located((By.XPATH, topics_xpath)))
                # ReadMore = browser.find_element_by_xpath(topics_xpath)
                ReadMore = WebDriverWait(browser, 10).until(
                    expected_conditions.element_to_be_clickable((By.XPATH, topics_xpath)))
                ReadMore.click()
            except:
                pass

            html = browser.page_source
            WholePage = get_page(html)
            ReviewBoxes = review_box(WholePage)
            for each in ReviewBoxes:
                ReviewInformation = {'link': link,
                                     'HotelName': hotel_name(WholePage),
                                     'HotelAddress': hotel_address(WholePage),
                                     'CountReviews': count_reviews(WholePage),
                                     'ReviewerName': reviewer_name(each),
                                     'ReviewerProfile': reviewer_profile(each),
                                     'ReviewID': review_id(each),
                                     'ReviewDate': review_date(each),
                                     'ReviewerLocation': reviewer_location(each),
                                     'ReviewerContribution': reviewer_contribution(each),
                                     'ReviewHelpfulVotes': review_helpful_votes(each),
                                     'ReviewStar': review_star(each),
                                     'ReviewText': review_text(each),
                                     'DateOfStay': date_of_stay(each),
                                     'TripType': trip_type(each),
                                     'RatingsDetail': ratings_detail(each),
                                     'ResponseDetails': response_details(each)}
                destination.write(ReviewInformation)
    browser.quit()

def scrape_first_pages():
    New_Review_linksPD = pd.read_csv('Outputs/hotels_with_reviews.csv')
    ReviewPageList = New_Review_linksPD.link.tolist()
    ReviewPageList.sort()
    ScrapeList = ReviewPageList[args.begin: args.end]
    with jsonlines.open(f'Outputs/{args.file}', args.overwrite) as destination:
        for link in tqdm(ScrapeList):
            html = open(os.path.join(DataLocation, link), encoding='utf-8').read()
            WholePage = get_page(html)
            ReviewBoxes = review_box(WholePage)
            for each in ReviewBoxes:
                ReviewInformation = {'link': link,
                                     'HotelName': hotel_name(WholePage),
                                     'HotelAddress': hotel_address(WholePage),
                                     'CountReviews': count_reviews(WholePage),
                                     'ReviewerName': reviewer_name(each),
                                     'ReviewerProfile': reviewer_profile(each),
                                     'ReviewID': review_id(each),
                                     'ReviewDate': review_date(each),
                                     'ReviewerLocation': reviewer_location(each),
                                     'ReviewerContribution': reviewer_contribution(each),
                                     'ReviewHelpfulVotes': review_helpful_votes(each),
                                     'ReviewStar': review_star(each),
                                     'ReviewText': review_text(each),
                                     'DateOfStay': date_of_stay(each),
                                     'TripType': trip_type(each),
                                     'RatingsDetail': ratings_detail(each),
                                     'ResponseDetails': response_details(each)}
                destination.write(ReviewInformation)


if __name__ == "__main__":
    if not args.first_pages:
        scrape_additional_pages()
    else:
        scrape_first_pages()
