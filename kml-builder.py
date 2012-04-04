#!/usr/bin/python
# -*- coding: utf-8 -*-
import geohash as geohasher

# http://toblerity.github.com/shapely/
from shapely.geometry import Polygon
from shapely.ops import cascaded_union

import sys
import os
import pprint
import time

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

class KmlBuilder:
  DATA_ROOT = "./data-root"
  countryCodes = dict()
  countrysPolygon = dict()
  poiFile = None
  heightMultiplier = 0

  def __init__(self, poiFile, heightMultiplier=1):
    print poiFile
    countryCodes = dict()
    with open("%s/ISO-3166-1.txt" % os.getcwd()) as f:
      content = f.readlines()
    for line in content:
      (code, name) = line.split(' ', 1)
      self.countryCodes[code] = name[:-1]
    self.poiFile = poiFile
    self.heightMultiplier = heightMultiplier

  def ccGeohashToDirname(self, ccGh):
    """ returns the {country-code:3}{geohash:5} as a string representing the
      desired directory struture """
    # Fastest: http://www.skymind.com/~ocrow/python_string/
    dirList = [ KmlBuilder.DATA_ROOT ]
    dirList.append("/")
    dirList.append(  ccGh[:3] )
    dirList.append("/")
    dirList.append( ccGh[3:6] )
    dirList.append("/")
    dirList.append( ccGh[6:7] )
    dirList.append("/")
    dirList.append( ccGh[7:8] )
    dirList.append("/")
    return ''.join(dirList)

  def dirnameToCcGeohash(self, dirname):
    return dirname.replace( KmlBuilder.DATA_ROOT, "" ).replace("/","")

  def dirnameToCountryCodeGeohash(self, dirname):
    ccGh = self.dirnameToCcGeohash(dirname)
    return ccGh[:3], ccGh[3:]



  def ensureDirectory(self, ccGh):
    """ Creates an appropriate directory from the {country-code:3}{geohash:5) if
      it does not exist. Note that filesystem caches are faster than trying to
      keep track of whether we have already created this - even on a spinning
      HDD, very much more so on an SSD. """
    dirname = self.ccGeohashToDirname(ccGh)
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


  def addToThisDirectory(self, dir, ppid):
    # TODO: use the proper os.join instead ...
    f = open(dir + "/" + ppid, "w")
    f.write(ppid)
    f.close()

  def addToDirectory(self, ppid):
    countryCode = None
    geohash = None
    # ppids look like this: 724ezjmd-e400738407474eb9b82e1e16ecb8efbc
    try:
      (cc_gh, uuid) = ppid.split('-')
      dir = self.ensureDirectory(cc_gh)
      self.addToThisDirectory(dir, ppid)
      countryCode = cc_gh[:3]
      geohash = cc_gh[3:6]
    except ValueError:
      pass
    return countryCode, geohash

  def addGeohashToCountry(self, countryCode, geohash):
    ''' using some complex geometry unioning here! '''
    if geohash is None:
      return
    # Here's an optimisation - without which a 45M POI run was taking well over
    # 12 hours. We're drawing the largest regions using 3-digit geohashs, and
    # each POI will live in one of these. The calculation of "within" is really
    # expensive and I'd like to avoid doing it - so to dramatically cut the
    # time, the best way is to dramatically cut the number of times it's done.
    if len(geohash) != 3:
      return
    b = geohasher.bbox(geohash)
    polygon = Polygon([
        (b['e'], b['n']), \
        (b['w'], b['n']), \
        (b['w'], b['s']), \
        (b['e'], b['s']), \
        (b['e'], b['n']) ])
    try:
      countryPolygon = self.countrysPolygon[countryCode]
      if not polygon.within(countryPolygon):
        #multipoly = cascaded_union([countryPolygon, polygon])
        multipoly = countryPolygon.union(polygon)
        self.countrysPolygon[countryCode] = multipoly
    except KeyError:
      self.countrysPolygon[countryCode] = polygon
    
  def createKmlWrapper(self, networkLinkControl, name, style, innerKML):
    return """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  %s
  <Document> 
    <name>%s</name>
    %s
    %s
  </Document>
</kml>""" % (networkLinkControl, name, style, innerKML)

  def geohashCoordinates(self, geohash, alt=0):
    """ Returns a string representing the coordinates of a geohash in a style
        suitable for using with Polygons, starting at the NE corner and moving
        in an anti-clockwise direction."""
    height = self.heightMultiplier * float(alt)
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

  def innerCountryKML(self, countryCode, innerDir):
    try:
      multipoly = self.countrysPolygon[countryCode] 
      bds = multipoly.bounds
      b = dict()
      b['w'] = str(bds[0])
      b['s'] = str(bds[1])
      b['e'] = str(bds[2])
      b['n'] = str(bds[3])
      coordinates = "%s,%s %s,%s %s,%s %s,%s %s,%s" % \
        (b['e'], b['n'], \
        b['w'], b['n'], \
        b['w'], b['s'], \
        b['e'], b['s'], \
        b['e'], b['n'])
      countryName = self.countryCodes[countryCode]
    except KeyError:
      coordinates = "0,0 0,0 0,0" 
      countryName = "country #%s" % countryCode
    return """
  <NetworkLink>
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
   </NetworkLink>""" % (countryName, b['n'], b['s'], b['e'], b['w'], innerDir)

  def innerGeohashKML(self, geohash, innerDir):
    bbox = geohasher.bbox(geohash)
    return """
  <NetworkLink>
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
    
  def writeGeohashKml(self, countryCode, geohash, innerGeohashs, innerPOIs, filename):
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
    numPoi = 0
    try:
      countryName = self.countryCodes[countryCode]
    except KeyError:
      countryName = "country #%s" % countryCode
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
    if geohash == "":
      try:
        multipoly = self.countrysPolygon[countryCode] 
        bds = multipoly.bounds
        b = dict()
        b['w'] = str(bds[0])
        b['s'] = str(bds[1])
        b['e'] = str(bds[2])
        b['n'] = str(bds[3])
        coordinates = "%s,%s %s,%s %s,%s %s,%s %s,%s" % \
          (b['e'], b['n'], \
          b['w'], b['n'], \
          b['w'], b['s'], \
          b['e'], b['s'], \
          b['e'], b['n'])
      except KeyError:
        coordinates = "0,0 0,0 0,0" 
      outerBorder = """  <Placemark>
      <name>%s outer bounding box</name>
      <description>%s</description>
      <styleUrl>#g0</styleUrl>
        <LineString>
          <extrude>0</extrude>
          <tessellate>1</tessellate>
          <coordinates>%s</coordinates>
        </LineString>
    </Placemark>""" % (countryName, message, coordinates)
    else:
      coordinates = self.geohashCoordinates(geohash, numPoi)
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

    # If we're the very root - where countryCode == "" - then instead of writing
    # innerGeohashKML we need to write innerCountryKML
    for innerGeohash in innerGeohashs:
      igName = innerGeohash["name"]
      igDir = innerGeohash["dir"]
      igNumPOI = innerGeohash["numPoi"]
      if countryCode == "":
        innerGeohashKml = self.innerCountryKML(igName, igDir)
      else:
        innerGeohashKml = self.innerGeohashKML(igName, igDir)
      innerKML = "%s%s" % (innerKML, innerGeohashKml)
    
    if geohash == "": 
      message = "%s has %d inner geohashs, and %d descendent POI" % \
        (countryName, len(innerGeohashs), numPoi)
      networkLinkControl = """  <NetworkLinkControl>
     <!--<message>This is KML file %s</message>-->
     <linkName>%s</linkName>
     <linkDescription>%s</linkDescription>
    </NetworkLinkControl>""" % (filename, countryName, message)
      geohash = countryCode
      if countryCode == "":
        filename = "%s/Nokia World POIs.kml" % self.DATA_ROOT
    # This enda the if geohash == ""

    kml = self.createKmlWrapper( networkLinkControl, geohash, style, innerKML )
    f = open(filename, "w")
    f.write(kml)
    f.close()

  def writeNumPOI(self, childPoi, dirname):
    f = open("%s/num.poi" % dirname, "w")
    f.write(str(childPoi))
    f.close()

  def readNumPOI(self, childPoi, dirname):
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
  def main(self):
    print "Reading POI file ... ",
    sys.stdout.flush()
    startMillis = int(round(time.time() * 1000))
    with open(self.poiFile, "r") as f:
      content = f.readlines()
    numPOI = len(content)
    endMillis = int(round(time.time() * 1000))
    print " read %d POI in %d millis. Adding geohash directories" \
        % (numPOI, (endMillis - startMillis)),
    print " (each dot is 1000):" 
    i = 0
    for line in content:
      if i % 1000 == 0:
        print ".",
        sys.stdout.flush()
      countryCode, geohash = self.addToDirectory(line.rstrip('\n'))
    print "\nAll POI added. Adding geohashs to countries:"

    i = 0
    pCC = ""
    w = os.walk( self.DATA_ROOT, topdown=False )
    try:
      t3 = w.next() 
      while True:
        # t3 is (dirpath, dirnames, filenames)
        (dirpath, dirnames, filenames) = t3
        countryCode, geohash = self.dirnameToCountryCodeGeohash(dirpath)
        if pCC != countryCode:
          print "%s (%d%%)" % (countryCode, int(100 * i / numPOI)),
          sys.stdout.flush()
          pCC = countryCode
        # this is the _real_ work of this portion!
        self.addGeohashToCountry(countryCode, geohash)
        i = i + 1
        t3 = w.next()
    except StopIteration:
      pass

    print "\nAll geohashs added. Building KML:"

    # The thing to do is to walk the filesystem
    w = os.walk( self.DATA_ROOT, topdown=False )

    pGeohash = "" # <- this is used for progress printing ...
    # take a look at http://docs.python.org/library/os.html
    try:
      t3 = w.next() 
      while True:
        # t3 is (dirpath, dirnames, filenames)
        (dirpath, dirnames, filenames) = t3

        # OK: so we need the geohash - not all dirs have geohashs - remember the
        # country codes and the root dir! 
        countryCode, geohash = self.dirnameToCountryCodeGeohash(dirpath)
        
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
          childPoi = self.readNumPOI(childPoi, os.path.join(dirpath, dirname))
          innerGeohash["numPoi"] = childPoi
          innerGeohashs.append(innerGeohash)
          
        kmlFilename = "%s/index.kml"% dirpath
        self.writeNumPOI(childPoi, dirpath)
        self.writeGeohashKml(countryCode, geohash, innerGeohashs, innerPOIs, kmlFilename)
        t3 = w.next()
    except StopIteration:   
      pass
    return 0

if __name__ == "__main__":
  kb = KmlBuilder(sys.argv[1])
  sys.exit(kb.main())

