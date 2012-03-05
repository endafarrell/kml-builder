#!/usr/bin/python
# -*- coding: utf-8 -*-
import geohash
import sys
import pprint
#import json
#import requests

# The "root" KML file shall be a set of folders containing the countries where
# our list of places are to be found. A small set therefore may not have all of
# the countries. As geohashs do not respect country borders[1], opening the
# country folder (or somehow[2] making it visible[2] will show those 3-digit
# geohashs which are at least partially contained by that country. Each 3-digit
# geohash is a KML region[3] and its subcontent is loaded by a NetworkLink[4]
# which allows the KML file to load what's needed when requested. A little work
# is needed to ensure that this works as expected. The NetworkLink that fills
# the 3-digit geohash/region makes visible the 4-digit geohash/regions within
# that country::3-digit geohash. The same applies for the 4-digit geohashes and
# the KML for the 5-digit geohashs/regions may well list all of the places
# within that country::5-digit geohash.
# [1] Difficult to show, but this code assumes that the places are identified as
#     {country:3}{geohash:5}-{!uuid}
# [2] https://developers.google.com/kml/documentation/kmlreference#open
# [3] https://developers.google.com/kml/documentation/kmlreference#region
# [4] https://developers.google.com/kml/documentation/kmlreference#networklink
#
# You will want to have python 2.7.2 (which on a Mac requires an update): please
# see http://www.python.org/download/releases/2.7.2/
#

def dumpGh3(gh3, data):
  if gh3 == '--data--':
    return
  bbox = geohash.bbox(gh3)
  data = str(int(data) * 500)
  print """
      <Placemark>
        <name>%s</name>
        <styleUrl>#s</styleUrl>
        <Polygon>
          <extrude>1</extrude>
          <altitudeMode>relativeToGround</altitudeMode>
          <outerBoundryIs>
            <LinearRing>
              <coordinates>
                %s,%s,%s
                %s,%s,%s
                %s,%s,%s
                %s,%s,%s
                %s,%s,%s
              </coordinates>
            </LinearRing>
          </outerBoundryIs>
        </Polygon>
      </Placemark>""" % ( gh3, \
          bbox['n'], bbox['e'], data, \
          bbox['n'], bbox['w'], data, \
          bbox['s'], bbox['w'], data, \
          bbox['s'], bbox['e'], data, \
          bbox['n'], bbox['e'], data )

def dumpCountry(cc):
  data = cc['--data--']
  print """
    <Folder id="%s">
      <name>%s</name>
      <description>The country of "%s" ("%s" code) has %s places</description>
      <visibility>1</visibility>
      <open>0</open>  """ % ( data['country-code'], \
          data['name'], data['name'], data['country-code'], \
          data['num-poi'] )
  for gh3 in cc:
    dumpGh3(gh3, cc[gh3])
  print """    </Folder>""" 

def dump(x):
  print """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document> 
    <Style id="s">
      <PolyStyle>
        <color>33000000</color>
        <colorMode>random</colorMode>
        <fill>1</fill>
      </PolyStyle>
    </Style>"""
  for cc in x:
    dumpCountry(x[cc])
  print """  </Document>
</kml>"""

countryCodes = dict()
with open('ISO-3166-1.txt') as f:
  content = f.readlines()
for line in content:
  (code, name) = line.split(' ', 1)
  countryCodes[code] = name[:-1]

with open('/Users/enda/Documents/KML/ppids') as f:
  content = f.readlines()

countries = dict()
for line in content:
  (cc_gh, uuid) = line.split('-')
  cc = cc_gh[:3]
  gh = cc_gh[4:8]
  gh3 = gh[:3]
  if cc in countries:
    ccGh = countries[cc]
    if gh3 in ccGh:
      ccGh[gh3] = ccGh[gh3] + 1
    else:
      ccGh[gh3] = 1
  else:
    countries[cc] = dict()
    countries[cc][gh3] = 1

for cc in countries:
  country = countries[cc]
  data = dict()
  data['name'] = countryCodes[cc]
  numPoi = 0
  for gh3 in country:
    numPoi = numPoi + country[gh3]
  data['num-poi'] = numPoi
  data['country-code'] = cc
  countries[cc]['--data--'] = data

dump(countries)
