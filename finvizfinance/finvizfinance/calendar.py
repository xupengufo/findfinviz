"""
.. module:: calendar
   :synopsis: calendar.

.. moduleauthor:: Tianning Li <ltianningli@gmail.com>
"""

import re
import json
from datetime import datetime
import pandas as pd
from finvizfinance.util import web_scrap


class Calendar:
    """Calendar
    Getting information from the finviz calendar page.
    """

    def __init__(self):
        """initiate module"""
        pass

    def calendar(self):
        """Get economic calendar table.

        Returns:
            df(pandas.DataFrame): economic calendar table
        """
        soup = web_scrap("https://finviz.com/calendar.ashx")
        
        data_script = None
        for script in soup.find_all("script"):
            text = script.text.strip()
            if text.startswith('{"data":'):
                data_script = text
                break

        if not data_script:
            return pd.DataFrame()

        data = json.loads(data_script)
        entries = data.get("data", {}).get("entries", [])
        
        importance_map = {1: "low", 2: "medium", 3: "high"}
        
        frame = []
        for e in entries:
            date_str = e.get("date", "")
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str)
                    datetime_val = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    datetime_val = date_str
            else:
                datetime_val = ""
                
            info_dict = {
                "Datetime": datetime_val,
                "Release": e.get("event", ""),
                "Impact": importance_map.get(e.get("importance"), ""),
                "For": e.get("reference") if e.get("reference") is not None else "",
                "Actual": e.get("actual") if e.get("actual") is not None else "",
                "Expected": e.get("forecast") if e.get("forecast") is not None else "",
                "Prior": e.get("previous") if e.get("previous") is not None else "",
            }
            frame.append(info_dict)
            
        return pd.DataFrame(frame)
