import os
import yelp
from instagram.client import InstagramAPI
import csv
import phonenumbers
import time
from flask import Flask, render_template, jsonify, redirect, flash, session, request
import jinja2
import datetime

app = Flask(__name__)
app.secret_key = "yoursecretkeyhere"


yelp_api = yelp.Api(
    consumer_key=os.environ['YELP_CONSUMER_KEY'],
    consumer_secret=os.environ['YELP_CONSUMER_SECRET'],
    access_token_key=os.environ['YELP_ACCESS_TOKEN'],
    access_token_secret=os.environ['YELP_ACCESS_TOKEN_SECRET'])

client_secret = os.environ["INSTAGRAM_CLIENT_SECRET"]
client_id = os.environ["INSTAGRAM_CLIENT_ID"]


def address_formatted(raw_address):
    address_string = ""
    for line in raw_address:
        address_string = address_string + line + ' '
    return address_string


def phone_formatted(raw_phone):
    phone_string = ""
    if raw_phone:
        phone_string = phonenumbers.parse(raw_phone, "US")
        phone_string = phonenumbers.format_number(phone_string, phonenumbers.PhoneNumberFormat.NATIONAL)
    return phone_string


def yelp_ids_hours_csv_to_dict():
    """Convert master list to dictionary"""

    yelp_ids_hours_file = open('insta9')
    yelp_ids_hours = csv.reader(yelp_ids_hours_file)

    yelp_ids_hours_dict = {}

    for row in yelp_ids_hours:
        infos = row[0].split('|')
        yelp_ids_hours_dict[infos[0]] = { \
        'Monday': infos[1], \
        'Tuesday': infos[2], \
        'Wednesday': infos[3], \
        'Thursday': infos[4], \
        'Friday': infos[5], \
        'Saturday': infos[6], \
        'Sunday': infos[7],
        'instalocation': infos[8] }

    return yelp_ids_hours_dict


def yelp_results_dict():
    """Call Yelp API to search for businesses on master list and 
    return dictionary of businesses and misc. info"""

    yelp_ids = sorted(yelp_ids_hours_csv_to_dict().keys())

    businesses = {}

    for yelp_id in yelp_ids:     # yelp_ids.keys() just all the yelp_ids
        business = yelp_api.GetBusiness(yelp_id)
        businesses[business.id] = { \
        'business_name': business.name.encode('ascii','ignore'), \
        'bus_lat': business.location.coordinate[u'latitude'], \
        'bus_long': business.location.coordinate[u'longitude'], \
        'address': address_formatted(business.location.address), \
        'phone': phone_formatted(business.phone)}

    return businesses


def preseed_healthynails():
    """Reading a Using SF Healthy Nail Salon List copied froms
    http://www.sfenvironment.org/healthy-nail-salon-program
    (Live map: http://www.sfenvironment.org/article/business/healthy-nail-salons)
    and returning a dictionary of yelp_ids"""

    healthynails_file = open('healthynails.csv')
    healthynails_businesses = csv.reader(healthynails_file)
    healthynails_dict = {}


    for row in healthynails_businesses:
        business_name = row[0]
        search_results = yelp_api.Search(term=business_name, limit=1, location="San Francisco, CA", categories="beautysvc,othersalons")
        for business in search_results.businesses:
            healthynails_dict[business.id] = business.name

    return healthynails_dict


def seed_manimap():
    """Use yelp_results_dict() to generate sitewide seed files"""

    businesses = yelp_results_dict()

    with open('dynamic.datas', 'wb') as xfile:
        writer = csv.writer(xfile, delimiter='|')
        for key, value in businesses.items():
            writer.writerow([key.encode('ascii', 'ignore'), \
                value['business_name'].encode('ascii', 'ignore'), \
                value['bus_lat'], \
                value['bus_long'], \
                value['address'], \
                value['phone'].encode('ascii', 'ignore')])

    healthy_nails_dict = preseed_healthynails()

    with open('healthy.nails', 'wb') as yfile:
        writer = csv.writer(yfile, delimiter='|')
        for key, value in healthy_nails_dict.items():
            writer.writerow([key.encode('ascii', 'ignore'), value.encode('ascii', 'ignore')])

    print "Site info has just been re-seeded"
    return "Site info has just been re-seeded"


def healthynails_dict():
    healthynails_dict = {}

    with open('healthy.nails', 'rb') as yfile:
        reader = csv.reader(yfile, delimiter='|')
        for row in reader:
            healthynails_dict[row[0]] = row[1]

    return healthynails_dict


def read_manimap():
    """Returns dictionary from sitewide seed file"""

    businesses = {}

    with open('dynamic.datas', 'rb') as xfile:
        reader = csv.reader(xfile, delimiter='|')
        for row in reader:
            businesses[row[0]] = { \
            'yelp_id': row[0], \
            'business_name': row[1], \
            'bus_lat': row[2], \
            'bus_long': row[3], \
            'address': row[4], \
            'phone': row[5]}

    return businesses


def salon_info_instapics(instalocation):
    api = InstagramAPI(client_id=client_id, client_secret=client_secret)

    recent_photos = {}
    recent_photos_5 = []

    recent_media, next = api.location_recent_media(location_id=instalocation)

    for media in recent_media:
        if len(recent_photos_5) < 5:
            pic = media.images[u'standard_resolution'].url.encode('ascii', 'ignore')
            link = media.link.encode('ascii', 'ignore')
            recent_photos_5.append([pic, link])
            place_name = media.location.name.encode('ascii', 'ignore')
            recent_photos[instalocation] = { place_name: recent_photos_5 }

    return recent_photos


@app.route('/')
def map():
    """Show map of businesses."""
    return render_template("map.html")

@app.route('/about')
def about_this():
    return render_template("about.html")


@app.route('/business_list.json')
def business_list():
    """JSON information about businessess.
    had to remove: la-crEme-spa-san-francisco-2, remEde-spa-san-francisco-2
    """
    now_datetime = datetime.datetime.now()
    today = now_datetime.strftime('%A')

    businesses = read_manimap()
    hours = yelp_ids_hours_csv_to_dict()
    businesses_for_map = {}

    for key, values in businesses.items():
        businesses_for_map[key] = values
        businesses_for_map[key].update({'todaysHours': hours[key][today]})

    return jsonify(businesses_for_map)


@app.route("/salons")
def list_salons():
    business_info = read_manimap()
    yelp_ids = sorted(business_info.keys())

    salons_yelp_ids_names = {}

    for yelp_id in yelp_ids:
        salons_yelp_ids_names[yelp_id] = business_info[yelp_id]['business_name']

    return render_template("salons_list.html", salons=salons_yelp_ids_names)


@app.route("/salons/<string:yelp_id>")
def show_salon(yelp_id):
    """Return page showing the details of a given salon"""
    # print yelp_id
    business_info = read_manimap()
    business_info = business_info[yelp_id]
    # print business_info
    business_name = business_info['business_name']
    address = business_info['address']
    phone = business_info['phone']

    openhours = {}
    hours_instalocation = yelp_ids_hours_csv_to_dict()[yelp_id]
    openhours['Monday'] = hours_instalocation['Monday']
    openhours['Tuesday'] = hours_instalocation['Tuesday']
    openhours['Wednesday'] = hours_instalocation['Wednesday']
    openhours['Thursday'] = hours_instalocation['Thursday']
    openhours['Friday'] = hours_instalocation['Friday']
    openhours['Saturday'] = hours_instalocation['Saturday']
    openhours['Sunday'] = hours_instalocation['Sunday']

    instalocation = hours_instalocation['instalocation']
    # salon_info_instapics(instalocation)
    recent_photos = salon_info_instapics(instalocation)  #[[url, src], [url, src]...]
    recent_photos_5 = recent_photos.values()[0].values()[0]
    # print recent_photos_5
    instaname = recent_photos.values()[0].keys()[0]

    healthynails = "hidden"

    for healthynails_salons in healthynails_dict().keys():
        # print type(healthnails_id_unicode)
        # healthynails_id_ascii = healthnails_id_unicode.encode('ascii','ignore')

        if healthynails_salons == yelp_id:
            healthynails = ""

    return render_template("salon_info.html", business_name=business_name, \
        address=address, phone=phone, openhours=openhours, recent_photos=recent_photos_5, \
        yelp_id=yelp_id, instaname=instaname, instalocation=instalocation, \
        healthynails=healthynails)


if __name__ == "__main__":
    app.config['DEBUG'] = True
    healthynails_dict()

    app.run()