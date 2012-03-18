#!/usr/bin/python
# -*- coding: utf-8 -*-
import geohash as geohasher
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
# TODO:
# 1/ Build a rainbow table of the geohashs. We don't _really_ need to keep
#    recomputing the 3,4 & 5 digit geohashs as they don't change - looking them
#    up ought to do nicely.

DATA_ROOT = "./data-root/"

countryCodes = dict()
with open('ISO-3166-1.txt') as f:
  content = f.readlines()
for line in content:
  (code, name) = line.split(' ', 1)
  countryCodes[code] = name[:-1]

""" returns the {country-code:3}{geohash:5} as a string representing the
    desired directory struture """
def ccGeohashToDirname(ccGh):
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

def dirnameToCcGeohash(dirname):
  return dirname.replace( DATA_ROOT, "" ).replace("/","")

def dirnameToGeohash(dirname):
  ccGh = dirnameToCcGeohash(dirname)
  return ccGh[3:]


""" Creates an appropriate directory from the {country-code:3}{geohash:5) if it
    does not exist """
def ensureDirectory(ccGh):
  dirname = ccGeohashToDirname(ccGh)
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

def createNetworkLink(dirname, geohash):
  bbox = geohasher.bbox(geohash)
  return """<NetworkLink>
    <name>%s</name>
    <Region>
      <LatLonAltBox>
        <north>%s</north>
        <south>%s</south>
        <east>%s</east>
        <west>%s</west>
      </LatLonAltBox>
      <Lod>
        <minLodPixels>128</minLodPixels>
        <maxLodPixels>1024</maxLodPixels>
      </Lod>
    </Region>
    <Link>
      <href>%s/index.kml</href>
      <viewRefreshMode>onRegion</viewRefreshMode>
    </Link>
  </NetworkLink>""" % ( \
      geohash, \
      bbox['n'], bbox['s'], bbox['e'], bbox['w'], \
      dirname)



def createMultiPlacemarks(geohash, numPOI):
  # TODO: wrap lest we have bad geohashs
  bbox = geohasher.bbox(geohash)
  latlng = geohasher.decode(geohash)
  data = str(numPOI * 500)
  return """
      <Placemark>
        <name>%s: %d POI</name>
        <Point>
          <coordinates>%s,%s,0</coordinates>
        </Point>
      </Placemark>
      <Placemark>
        <name>%s</name>
        <styleUrl>#s</styleUrl>
        <visibility>1</visibility>
        <Polygon>
          <extrude>1</extrude>
          <altitudeMode>relativeToGround</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                %s,%s,%s
                %s,%s,%s
                %s,%s,%s
                %s,%s,%s
                %s,%s,%s
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>""" % ( \
          geohash, numPOI, \
          latlng[1], latlng[0], \
          geohash, \
          bbox['e'], bbox['n'], data, \
          bbox['w'], bbox['n'], data, \
          bbox['w'], bbox['s'], data, \
          bbox['e'], bbox['s'], data, \
          bbox['e'], bbox['n'], data )

def createKmlWrapper(innerKML):
  return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document> 
    <Style id="s">
      <PolyStyle>
        <color>7dff0000</color>
        <colorMode>normal</colorMode>
        <fill>1</fill>
      </PolyStyle>
    </Style>
    %s
  </Document>
</kml>""" % innerKML

# The start: read the list of {ppid}s and add the appropriate content to the
# directories
with open('/Users/enda/Documents/KML/ppids') as f:
  content = f.readlines()

for line in content:
  addToDirectory(line.rstrip('\n'))

# The thing to do now is to walk the filesystem
w = os.walk( DATA_ROOT, topdown=False)
pGeohash = ""
# take a look at http://docs.python.org/library/os.html
# In this first pass, we look for the data points only
try:
  t3 = w.next() 
  while True:
    # t3 is (dirpath, dirnames, filenames)
    (dirpath, dirnames, filenames) = t3

    # OK: so we need the geohash - not all dirs have geohashs - remember the
    # country codes and the root dir! 
    geohash = dirnameToGeohash(dirpath)
    
    if len(geohash) > 2:
      print "\b" * (2 + len(pGeohash)),
      print geohash,
      pGeohash = geohash
      sys.stdout.flush()

    # As this is taken bottom up, we get a list of the POI under the geohash.
    # In this first pass, I will only be gathering the number of POI and making
    # an extrusion based on that number.

    # How many of the files are "POI" {ppid}s? POI have a given length. Note
    # that this number does not include the decendents!
    numPOI = 0
    for filename in filenames:
      if len(filename) == 41:
        numPOI = numPOI + 1
      if numPOI > 0:
        # At this early stage, I do not want to create KML for empty nor
        # higher-level geohashs
        kml = createKmlWrapper(createMultiPlacemarks(geohash, numPOI))
        f = open( "%s/index.kml"% dirpath, "w")
        f.write(kml)
        f.close()

    t3 = w.next()
except StopIteration:   
  pass

print "\nProcessing index files"
w = os.walk( DATA_ROOT, topdown=False)
pdirpath = ""
# In this pass, we handle the "index" KML files only
try:
  t3 = w.next() 
  while True:
    # t3 is (dirpath, dirnames, filenames)
    (dirpath, dirnames, filenames) = t3

    print "\b" * (2 + len(pdirpath)),
    print dirpath,
    pdirpath = dirpath
    sys.stdout.flush()

    geohashRoot = dirnameToGeohash(dirpath)
    #if geohashRoot == "":
    #  t3 = w.next()
    #  continue

    if "index.kml" in filenames:
      t3 = w.next()
      continue

    networkLinks = ""
    for dirname in dirnames:
      # Create a network-link based parent KML
      geohash = geohashRoot + dirname
      networkLinks = networkLinks \
          + createNetworkLink(dirname, geohash)
    kml = createKmlWrapper(networkLinks)
    f = open("%s/index.kml" % dirpath, "w")
    f.write(kml)
    f.close()

    t3 = w.next()
except StopIteration:   
  pass

print "\nFinished"
sys.exit()

