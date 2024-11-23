#!/usr/bin/env python3

# Copyright (c) 2013, Corvil Limited. All rights reserved.
# THIS SOURCE CODE IS A TRADE SECRET OF CORVIL AND SHOULD NOT BE TRANSFERRED
# OR DISCLOSED TO ANY THIRD PARTY WITHOUT CORVIL'S PERMISSION. THIS SOURCE
# CODE IS LICENSED "AS IS", SOLELY FOR ILLUSTRATION PURPOSES, ONLY WITHIN
# THE LIMITED, SPECIFIC CONTEXT AND PARAMETERS INDICATED IN THE APPLICABLE
# CORVIL INSTRUCTIONS AND DOCUMENTATION, AND SUBJECT TO THE TERMS AND
# CONDITIONS OF THE CORVIL STANDARD SOFTWARE LICENSE AGREEMENT, INCLUDING
# WITHOUT LIMITATION THE LIABILITY LIMITATIONS SET FORTH THEREIN.

# NB: this was developed against Python v3.6

# Version: 3.2.0.202206301037-GA+273102
class Stat(dict):
    """
    The Stat object contains stat fields

    Attributes:
        direction (str): request or response
        stat_name (str) : name of the stat
        unit (str) : unit used to convey information about this stat
        aspect (str): aspect used
        percentile_value (str) : percentile value used.
    """
    direction = ""
    stat_name = ""
    unit = ""
    aspect = ""
    percentile_value = ""
    factor = ""
    type = ""


class DataFields(object):
    def __init__(self, values, names=[], cne=None):
        self.names = names
        self.values = values
        self.cne = cne

class LensDataResponse(object):
    def __init__(self, time_range):
        self.time_range = time_range
        self.group_by = []
        self.stats = []
        self.data = []
        self.add_cne = False

    def __get_stat(self, stat_name, meta):
        """Check stat attribute exist else return empty.
        Return:
            string: empty string or value
        """
        return meta[stat_name] if stat_name in meta else ""

    def __add_tag_data(self, names, tag, grouping_index):
        if "tag" in tag or "session" in tag:
            grouping_index = grouping_index + 1
            tag_element = tag.tag if "tag" in tag else tag.session
            for child_tag in tag_element:
                names[grouping_index] = child_tag["_name"]
                child_tag_obj = DataFields(child_tag["_values"], names=[*names])
                if "_cne" in child_tag:
                    self.add_cne = True
                    child_tag_obj.cne = child_tag["_cne"]
                self.data.append(child_tag_obj)
                self.__add_tag_data([*names], child_tag, grouping_index)

    def init_from_response(self, response):
        for meta in response["metadata"].stats.stat:
            stat = Stat()
            stat.direction=self.__get_stat("_direction", meta)
            stat.stat_name=self.__get_stat("_name", meta)
            stat.unit=self.__get_stat("_unit", meta)
            stat.type=self.__get_stat("_type", meta)
            stat.aspect=self.__get_stat("_aspect", meta)
            stat.percentile_value=str(self.__get_stat("_percentileValue", meta))
            stat.factor=self.__get_stat("_factor", meta)
            self.stats.append(stat)

        for groupBy in response["metadata"].groupBy:
            if hasattr(groupBy, "_sessions"):
                self.group_by.append("Sessions")
            else:
                self.group_by.append(groupBy["_tagType"])

        for time_range in response["data"].timeRange:
            if "tag" in time_range:
                for tag in time_range.tag:
                    names = [None] * len(self.group_by)
                    names[0] = tag["_name"]
                    tag_obj = DataFields(tag["_values"], names=names)
                    self.data.append(tag_obj)
                    self.__add_tag_data([*names], tag, 0)

            elif "session" in time_range:
                for session in time_range.session:
                    session_obj = DataFields(session["_values"], names=[session["_name"]])
                    if "_cne" in session:
                        self.add_cne = True
                        session_obj.cne = session["_cne"]
                    self.data.append(session_obj)

    def __format_aspect(self, aspect):
        if aspect == "percentile":
            return "pctl"
        return aspect

    def __format_unit(self, unit):
        unit_format = "(%s)"
        if unit == "bps":
            return unit_format %"kbits/s"
        elif unit == "pps":
            return unit_format %"pkts/s"
        elif unit:
            return unit_format % unit
        else:
            return ""

    def value_to_str(self, value, factor=1):
        try:
            if factor != 0:
                return int(value) / int(factor)
            else:
                return value
        except ValueError:
            return ''
        except TypeError:
            return ''

    def to_csv(self):
        group_by_header = []
        group_by_header.extend(self.group_by)
        group_by_header[0] = "#Grouping:" + group_by_header[0]
        yield group_by_header
        header_row = []
        header_row.extend(self.group_by)
        if self.add_cne:
            header_row.append("Cne")
        for stat in self.stats:
            direction = "->" if stat.direction == "request" else "<-"
            stat_name = stat.stat_name if stat.stat_name else stat.type
            percentile = "%s" % stat.percentile_value if stat.percentile_value else ""
            aspect = self.__format_aspect(stat.aspect) if stat.aspect else ""
            unit = self.__format_unit(stat.unit)
            row = "{} {} {} {} {}".format(direction, stat_name, percentile, aspect, unit)
            header_row.append(row)
        yield header_row

        for data in self.data:
            values = data.values.replace("-", "").split(" ")
            index = 0
            for stat in self.stats:
                values[index] = self.value_to_str(values[index], stat.factor)
                index = index +1
            if self.add_cne:
                record = [*data.names, data.cne,  *values]
            else:
                record = [*data.names,  *values]
            yield record
