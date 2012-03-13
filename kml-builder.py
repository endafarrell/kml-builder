#!/usr/bin/python
# -*- coding: utf-8 -*-
import geohash
import sys
import os
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
# The way this works is essentially a "file/folder"-based approach as follows:
# 1/ Iterate over each place
# 2/ -- for each {country:3} create a {country:3} dir
# 3/ -- for each {geohash:5:-3} create a {geohash:5:-3} dir
#       (eg, for the {ppid} "724ezjmd-e400738407474eb9b82e1e16ecb8efbc" the
#       following sub-direcotries are created:
#       data/
#       ⊢--- 724/
#       |    ⊢--- ezj
#       |    |    ⊢---- m
#       |    |    |     ⊢--- d
#       |    |    |     |    ⊢--- 724ezjmd-e400738407474eb9b82e1e16ecb8efbc.kml
#       The design is to start with countries (the ./data/{country:3}/ dirs, and
#       within these I have found that visually (on a global scale) that a
#       3-digit geohash is most appealing - hence
#       ./data/{country:3}/{geohash:3}. In nearly RESTful fashion, the sub
#       directories are found with a simple lookup strategy. 
# 4/ Once the directories are populated, they are iterated over to build
#    directory-specific metadata. 

DATA_ROOT = "./data-root/"

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

""" returns the {country-code:3}{geohash:5} as a string representing the
    desired directory struture """
def ccGhToDirname(ccGh):
  # Fastest: http://www.skymind.com/~ocrow/python_string/
  dirList = [ DATA_ROOT ]
  dirList.append(  ccGh[:3] )
  dirList.append("/")
  dirList.append( ccGh[3:6] )
  dirList.append("/")
  dirList.append( ccGh[6:7] )
  dirList.append("/")
  dirList.append( ccGh[7:8] )
  dirList.append("/")
  return ''.join(dirList)

""" Creates an appropriate directory from the {country-code:3}{geohash:5) if it
    does not exist """
def ensureDirectory(ccGh):
  dirname = ccGhToDirname(ccGh)
  try:
    os.makedirs(dirname)
  except OSError:
    if os.path.exists(dirname):
      # We are nearly safe
      pass
    else:
      # There was an error on creation, so make sure we know about it
      raise
  return dirname


def addToThisDirectory(dir, ppid):
  f = open(dir + "/" + ppid, "w")
  f.write(ppid)
  f.close()

def addToDirectory(ppid):
  # ppids look like this: 724ezjmd-e400738407474eb9b82e1e16ecb8efbc
  try:
    (cc_gh, uuid) = ppid.split('-')
    dir = ensureDirectory(cc_gh)
    addToThisDirectory(dir, ppid)
  except ValueError:
    pass

# The start: read the list of {ppid}s and add the appropriate content to the
# directories
with open('/Users/enda/Documents/KML/ppids') as f:
  content = f.readlines()

for line in content:
  addToDirectory(line.rstrip('\n'))

# The thing to do now is to walk the filesystem
w = os.walk( DATA_ROOT, topdown=False)
# take a look at http://docs.python.org/library/os.html

sys.exit()

"""
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
"""

