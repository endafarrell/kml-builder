#!/usr/bin/python
# -*- coding: utf-8 -*-
import geohash as geohasher
import sys
import os
import pprint
#import json
#import requests
# Note: not using pyKML as the dependencies for lxml are not acceptable at this
# time on my machine, hence manual building of KML. As all of the KML being used
# here is quite simple, that's not a major problem.

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

def ccGeohashToDirname(ccGh):
  """ returns the {country-code:3}{geohash:5} as a string representing the
    desired directory struture """
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

def dirnameToCountryCodeGeohash(dirname):
  ccGh = dirnameToCcGeohash(dirname)
  return ccGh[:3], ccGh[3:]



def ensureDirectory(ccGh):
  """ Creates an appropriate directory from the {country-code:3}{geohash:5) if it
    does not exist. Note that filesystem caches are faster than trying to keep
    track of whether we have already created this - even on a spinning HDD, very
    much more so on an SSD. """
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

def createKmlWrapper(networkLinkControl, name, style, innerKML):
  return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  %s
  <Document> 
    <name>%s</name>
    %s
    %s
  </Document>
</kml>""" % (networkLinkControl, name, style, innerKML)

def geohashCoordinates(geohash, alt=0):
  """ Returns a string representing the coordinates of a geohash in a style
      suitable for using with Polygons, starting at the NE corner and moving
      in an anti-clockwise direction."""
  height = 500 * float(alt)
  bbox = geohasher.bbox(geohash)
  return """%s,%s,%d
              %s,%s,%d
              %s,%s,%d
              %s,%s,%d
              %s,%s,%d""" % ( \
        bbox['e'], bbox['n'], height, \
        bbox['w'], bbox['n'], height, \
        bbox['w'], bbox['s'], height, \
        bbox['e'], bbox['s'], height, \
        bbox['e'], bbox['n'], height )

def innerGeohashKML(geohash, innerDir):
  bbox = geohasher.bbox(geohash)
  return """  <NetworkLink>
    <name>%s</name>
    <Region>
      <LatLonAltBox>
        <north>%s</north>
        <south>%s</south>
        <east>%s</east>
        <west>%s</west>
      </LatLonAltBox>
      <Lod>
        <minLodPixels>32</minLodPixels>
        <maxLodPixels>768</maxLodPixels>
      </Lod>
    </Region>
    <Link>
      <href>./%s/index.kml</href>
      <viewRefreshMode>onRegion</viewRefreshMode>
    </Link>
  </NetworkLink>""" % (geohash, bbox['n'], bbox['s'], bbox['e'], bbox['w'], innerDir)
  
def writeGeohashKml(geohash, innerGeohashs, innerPOIs, filename):
  """ What's needed to build a geohash's KML? The following:
    1/ geohash being drawn. Usage:- to set the Camera and the LineRing (for
         outer border) in the NetworkLinkControl, and the name
       for this.
    2/ innerGeohashs found within this geohash. This is a list of dicts - the
       inner geohash name and other details. These are used
       to create both Polygons and NetworkLinks to the next level of detail.
    3/ innerPOIs found within this geohash. This is a list of tuples - the POI
       and whatever details are to be shown about the POI.
    4/ filename - to help understand whic KML file is actually on-screen.
    Note that there is a similarity with what os.walk gives here - with the first
    three parameters - not initially on purpose, but it makes sense."""
  # NOTE: when the geohash == "" (the empty string) we are really dealing with
  # a country and not a geohash. This is not dealt with properly yet.
  numPoi = 0
  for innerGeohash in innerGeohashs:
    numPoi = numPoi + innerGeohash["numPoi"]
  message = "%s has %d inner geohashs, %d direct POI and %d descendent POI" % (geohash, \
        len(innerGeohashs), len(innerPOIs), numPoi)
  networkLinkControl = """  <NetworkLinkControl>
   <!--<message>This is KML file %s</message>-->
   <linkDescription><![CDATA[%s]]></linkDescription>
  </NetworkLinkControl>""" % (filename, message)
  # Note that the networkLinkControl could also have the following:
  # <linkName>New KML features</linkName>
  # <linkDescription><![CDATA[KML now has new features available!]]></linkDescription>
  # TODO: add the Camera element to this.
  coordinates = geohashCoordinates(geohash, numPoi)
  outerBorder = """  <Placemark>
    <name>%s outer border</name>
    <description>%s</description>
    <styleUrl>#g%d</styleUrl>
    <MultiGeometry>
      <LineString>
        <extrude>0</extrude>
        <tessellate>1</tessellate>
        <coordinates>%s</coordinates>
      </LineString>
      <Polygon>
        <extrude>1</extrude>
        <altitudeMode>relativeToGround</altitudeMode>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>%s</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </MultiGeometry>
  </Placemark>""" % (geohash, message, len(geohash), coordinates, coordinates)
  style = """<Style id="g3">
      <PolyStyle>
        <color>281400FF</color>
        <colorMode>normal</colorMode>
        <fill>1</fill>
      </PolyStyle>
    </Style>
    <Style id="g4">
      <PolyStyle>
        <color>2814B4FF</color>
        <colorMode>normal</colorMode>
        <fill>1</fill>
      </PolyStyle>
    </Style>
    <Style id="g5">
      <PolyStyle>
        <color>1414F0FF</color>
        <colorMode>normal</colorMode>
        <fill>1</fill>
      </PolyStyle>
    </Style>"""
  innerKML = outerBorder
  for innerGeohash in innerGeohashs:
    igName = innerGeohash["name"]
    igDir = innerGeohash["dir"]
    igNumPOI = innerGeohash["numPoi"]
    innerGeohashKml = innerGeohashKML(igName, igDir)
    innerKML = "%s%s" % (innerKML, innerGeohashKml)
  
  kml = createKmlWrapper(networkLinkControl, geohash, style, innerKML)
  f = open(filename, "w")
  f.write(kml)
  f.close()

def writeNumPOI(childPoi, dirname):
  f = open("%s/num.poi" % dirname, "w")
  f.write(str(childPoi))
  f.close()

def readNumPOI(childPoi, dirname):
  try:
    f = open("%s/num.poi" % dirname, "r")
    poi = f.readline()
    f.close()
    childPoi = childPoi + int(poi)
  except IOError:
    pass
  return childPoi

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
    countryCode, geohash = dirnameToCountryCodeGeohash(dirpath)
    
    if len(geohash) > 2:
      print "\b" * (2 + len(pGeohash)),
      print geohash,
      pGeohash = geohash
      sys.stdout.flush()


    # How many of the files are "POI" {ppid}s? POI have a given length. Note
    # that this number does not include the decendents!
    innerGeohashs = []
    innerPOIs = []
    for filename in filenames:
      if len(filename) == 41:
        innerPOIs.append(filename)
    childPoi = len(innerPOIs)
    for dirname in dirnames:
      innerGeohash = dict()
      innerGeohash["name"] = "%s%s" % (geohash, dirname)
      innerGeohash["dir"] = dirname
      childPoi = readNumPOI(childPoi, os.path.join(dirpath, dirname))
      innerGeohash["numPoi"] = childPoi
      innerGeohashs.append(innerGeohash)
      
    kmlFilename = "%s/index.kml"% dirpath
    writeNumPOI(childPoi, dirpath)
    writeGeohashKml(geohash, innerGeohashs, innerPOIs, kmlFilename)
    t3 = w.next()
except StopIteration:   
  pass

print "\nFinished"
sys.exit()

