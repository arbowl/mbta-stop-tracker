# mbta-stop-tracker
A GUI to select T stops and provide arrival times for users to minimize time spent waiting at stations

# Logic

json file to create these dictionaries:

dict lines = (
    'Green Line (B)' : 'Green-B',
    'Green Line(C) : 'Green-C',
    ...
)

dict routes = (
    'Green-B' : ['Chiswick Rd.', 'Sutherland', ... ],
    'Green-C' : ['Cleveland Circle', 'Tappan St.', ... ],
    ...
)

dict stops = (
    'Chiswick Rd.' : 'place-chswk',
    'St. Mary's St.' : 'place-smarys',
    ...
)

"Route" dropdown is populated by "lines" dict
When "Route" selected, "Stops" drowndown is populated by "routes" dict
When "Stops" selected, URL is constructed via "lines" and "stops" keys

MBTA object = 
  route  = 'Green-D'
  stop = 'place-fenwy'
  direction = '0'
  method = 'predictions'
  
  def make_url():
    return url
