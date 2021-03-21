# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.embed import json_item
def bokeh_handler(request):
    data = request.get_json(silent=True)
    categories = []
    counts = []
    for item in data.items():
        categories.append(item[0])
        counts.append(int(item[1]))
    # Create the plot
    p = figure(x_range=categories, title="Fruit counts", toolbar_location=None, tools="")
    p.vbar(x=categories, top=counts, width=0.9)
    p.xgrid.grid_line_color = None
    p.y_range.start = 0
    # Send message to server
    return {
        "statusCode": 200,
        "body": json.dumps(json_item(p)),
        "headers": {
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST'
        }
    }
