"""
===============================================================================

Developed by Tariq Shihadah
tariq.shihadah@gmail.com

Created:
10/22/2019

Modified:
2/10/2021

===============================================================================
"""


################
# DEPENDENCIES #
################


import numpy as np
from shapely.geometry import LineString, MultiLineString
import shapely
#from htspy.linref.range import RangeCollection
from rangel import RangeCollection
import copy, math


#############
# MLS ROUTE #
#############


class MLSRoute(object):
    """
    An object class to manage route mile-post information for each vertex of a
    shapely MultiLineString (MLS). An MLSRoute object instance will be able to
    convert between the actual linear distance along an MLS (starting from the
    origin of the MLS and moving downstream along the line, ignoring spaces 
    between individual LineStrings) to the route distance along the MLS based
    on provided route break information.
    
    Parameters
    ----------
    mls : shapely MultiLineString
        The linear geometry being represented by the route object.
    rte_ranges : list of tuples of numerical values
        Numerical information representing the start and end distance values
        for each LineString in the MultiLineString. If rte_ranges is used, 
        rte_breaks will be automatically computed and should not be input.
    rte_breaks : list of lists of numerical values
        Numerical information representing the route distance values at each
        vertice of the route MultiLineString. To include breaks in route 
        values, input a separate list for each contiguous group of vertices. 
        Each list should have a number of elements equal to the number of 
        vertices in each LineString contained in the MultiLineString. If 
        rte_breaks is used, rte_ranges should not be input.
    closed : str {'left', 'right', 'both', 'neither'}, default 'both'
        Whether intervals are closed on the left-side, 
        right-side, both or neither.
    """
    
    def __init__(self, mls, rte_ranges=None, rte_breaks=None, closed='both',
                 **kwargs):
        
        # Confirm valid input MLS
        if not isinstance(mls, MultiLineString):
            if isinstance(mls, LineString):
                mls = MultiLineString([mls])
            else:
                raise TypeError("Input geometry must be a shapely \
MultiLineString or LineString.")
        self._mls = mls
        
        # Confirm valid closed selection
        if not closed in ('left', 'right', 'both', 'neither'):
            raise ValueError("Closed selection must be 'left', 'right', \
'both', or 'neither'.")
        else:
            self._closed = closed
            
        # Confirm valid input route values
        # - Using route ranges information
        if not rte_ranges is None:
            # Coerce as numpy array, check shape
            try:
                rte_ranges = np.asarray(rte_ranges)
            except:
                raise TypeError("Input ranges should be array-like of \
numeric values with a shape of (n,2) where n equals the number of lines in \
the provided MultiLineString.")
            if not rte_ranges.shape == (len(mls), 2):
                raise ValueError("Input ranges should be array-like of \
numeric values with a shape of (n,2) where n equals the number of lines in \
the provided MultiLineString.")
            # Convert to breaks
            self._rte_breaks = self._ranges_to_breaks(rte_ranges)
            _input_route_values = True
        
        # - Using route breaks information
        elif not rte_breaks is None:
            # Check shape
            try:
                rte_breaks = [np.asarray(x) for x in rte_breaks]
            except:
                raise TypeError("Input breaks should be list of array-like \
of numeric values with lengths equal to the number of vertices in each \
corresponding line in the provided MultiLineString.")
            if not [len(x) for x in rte_breaks] == \
                [len(l.coords) for l in mls]:
                raise TypeError("Input breaks should be list of array-like \
of numeric values with lengths equal to the number of vertices in each \
corresponding line in the provided MultiLineString.")
            # Log values
            self._rte_breaks = rte_breaks
            _input_route_values = True
                
        # - No breaks information given, raise error
        else:
            _input_route_values = False
        
        # Define the ranges associated with the input route information
        if _input_route_values:
            
            self._mls_ranges = self._define_mls_ranges()
            self._rte_ranges = self._define_rte_ranges()
        else:
            self._mls_ranges = self._define_mls_ranges()
            self._rte_breaks = self._mls_breaks.copy()
            self._rte_ranges = self._mls_ranges.copy()
        
    def __len__(self):
        return self.rte_length
    
    def __str__(self):
        return 'MLSRoute('+str(self.mls)+')'
        
    @property
    def mls(self):
        return self._mls
    
    @property
    def rte_length(self):
        return self.rte_ranges.total_length
    
    @property
    def mls_length(self):
        try:
            return self._mls_length
        except AttributeError:
            self._mls_length = self.mls.length
            return self._mls_length
    
    @property
    def num_lines(self):
        try:
            return self._num_lines
        except AttributeError:
            self._num_lines = len(self.mls)
            return self._num_lines
    
    @property
    def mls_breaks(self):
        return self._mls_breaks
        
    @property
    def rte_breaks(self):
        return self._rte_breaks
        
    @property
    def mls_ranges(self):
        try:
            return self._mls_ranges
        except AttributeError:
            self._mls_ranges = self._define_mls_ranges()
            return self._mls_ranges
    
    @property
    def rte_ranges(self):
        try:
            return self._rte_ranges
        except AttributeError:
            self._rte_ranges = self._define_rte_ranges()
            return self._rte_ranges
    
    @property
    def vertices(self):
        try:
            return self._vertices
        except AttributeError:
            self._vertices = [np.insert(x.cumsum(),0,0) \
                              for x in self.element_lengths]
            return self._vertices
    
    @property
    def element_lengths(self):
        try:
            return self._element_lengths
        except AttributeError:
            self._element_lengths = self._compute_element_lengths()
            return self._element_lengths
        
    @property
    def closed(self):
        return self._closed
    
    @classmethod
    def from_2d_paths(cls, paths, **kwargs):
        """
        Create MLSRoute instance from a list of paths, made up of a list of 
        three-element tuples with X, Y, and range location (i.e., M-value).
        """
        # Parse input paths into LineStrings and route breakpoint information
        lines  = []
        breaks = []
        for path in paths:
            lines.append(LineString([(x[0], x[1]) for x in path]))
            breaks.append([x[2] for x in path])
        
        # Return generated MLSRoute instance based on input paths
        return cls(MultiLineString(lines), rte_breaks=breaks, **kwargs)
    
    @classmethod
    def from_lines(cls, lines, begs, ends, **kwargs):
        """
        Create an MLSRoute instance from a list of LineStrings or a single 
        MultiLineString and lists of begin and end mile post values with 
        lengths equal to the number of LineStrings within the provided 
        geometry.
        
        Parameters
        ----------
        lines : MultiLineString, LineString, or list of either
            A collection of shapely linear geometries (LineStrings or 
            MultiLineStrings) to use as the basis for the MLSRoute.
        begs : list of numeric values or a single numeric value
            A list of begin mile post values equal in length to the provided 
            lines. This correlates to a single begin mile post value for each 
            linear geometry in the provided collection. If a single mile post 
            value is provided, begin mile post values for multiple lines will 
            be linearly interpolated.
        ends : list of numeric values or a single numeric value
            A list of end mile post values equal in length to the provided 
            lines. This correlates to a single end mile post value for each 
            line in the provided collection. If a single mile post value is 
            provided, end mile post values for multiple lines will be 
            linearly interpolated.
        **kwargs
            Keyword arguments to be input in the MLSRoute constructor.
        """
        # Single geometry provided
        # - LineString
        if isinstance(lines, LineString):
            full_lines = [MultiLineString([lines])]
        # - MultiLineString
        elif isinstance(lines, MultiLineString):
            full_lines = [lines]
        # List of geometries provided
        elif isinstance(lines, list) or isinstance(lines, tuple):
            # - LineStrings
            if all(isinstance(i, LineString) for i in lines):
                full_lines = [MultiLineString(lines)]
            # - MultiLineStrings
            elif all(isinstance(i, MultiLineString) for i in lines):
                full_lines = lines
        else:
            raise TypeError("Input lines must be valid shapely linear "
                            "geometries or list or tuple of the same. Provided "
                            f"lines are of type {type(lines)}.")
        
        # Ensure valid breaks information provided
        # - Enforce list-data
        try:
            begs = list(begs)
        except TypeError:
            begs = [begs]
        try:
            ends = list(ends)
        except TypeError:
            ends = [ends]
            
        # Check for input type
        # - Single begin/end point provided
        if len(begs) == len(ends) == 1:
            full_lines = combine_mpgs(full_lines, cls=MultiLineString)
            distributed = \
                _distribute_dimensions(full_lines, begs[0], ends[0])
            ranges = np.stack([distributed[0], distributed[1]]).T
        # - One begin/end point per MultiLineString provided
        elif len(begs) == len(ends) == len(full_lines):
            begs_new = []
            ends_new = []
            for line, beg, end in zip(full_lines, begs, ends):
                distributed = \
                    _distribute_dimensions(line, beg, end)
                begs_new.extend(list(distributed[0]))
                ends_new.extend(list(distributed[1]))
            full_lines = combine_mpgs(full_lines, cls=MultiLineString)
            ranges = np.stack([begs_new, ends_new]).T
        # - One begin/end point per LineString provided
        elif len(begs) == len(ends) == sum(len(i) for i in full_lines):
            ranges = np.stack([begs, ends]).T
            full_lines = combine_mpgs(full_lines, cls=MultiLineString)
        # - Invalid input type
        else:
            raise ValueError(f'Must provide a number of begin and \
end mile post values equal to the number of lines if providing multiple \
values. Provided: {len(begs):,.0f} begs, {len(ends):,.0f} ends, \
{len(mls):,.0f} lines.')
        
        # Return generated MLSRoute instance based on input parameters
        return cls(full_lines, rte_ranges=ranges, **kwargs)

    @classmethod
    def concatenate(cls, routes, **kwargs):
        """
        Combine a list of MLSRoute objects into a single MLSRoute.

        NOTE:
        - MLSRoute objects will be concatenated in the order they are 
          provided.
        - Behavior of this method under non-trivial conditions has not been 
          tested.
        """
        # Validate input
        try:
            for route in routes:
                assert isinstance(route, cls)
        except:
            raise TypeError("Input routes must be list-like of MLSRoute \
class instances.")
        
        # Combine route breaks
        rte_breaks = \
            [rte_break for route in routes for rte_break in route.rte_breaks]
        # Combine MLS geometries
        mls = combine_mpgs(\
            [route.mls for route in routes], cls=MultiLineString)
        # Generate MLS Route instance
        mr = cls(mls, rte_breaks=rte_breaks, **kwargs)
        return mr

    def _compute_element_lengths(self):
        """
        Get individual lengths of each linear element of the route 
        MultiLineString.
        """
        # Store all vectors
        lengths = []
        for line in self.mls:
            # Log vector length
            coords = line.coords
            lengths.append(np.asarray([LineString(coords[i-1:i+1]).length \
                                       for i in range(1, len(coords))]))
        return lengths
    
    def _ranges_to_breaks(self, ranges):
        """
        """
        all_breaks = []
        for lengths, rng in zip(self.element_lengths, ranges):
            try:
                delta = rng[-1] - rng[0]
            except IndexError:
                raise IndexError("Input route ranges information must be \
provided as a list of tuples of start and end values.")
            lengths = lengths / lengths.sum() # Normalize
            lengths = (lengths.cumsum() * delta) + rng[0]
            lengths[-1] = rng[-1] # Snap last value to range bound
            all_breaks.append(np.concatenate([rng[0], lengths], axis=None))
        return all_breaks
    
    def _define_mls_ranges(self):
        """
        Generate range collection for multilinestring vertice distances.
        """
        
        # Accumulate vector lengths to generate range collection by breaks
        self._mls_breaks = np.concatenate([[0]] + \
                                          self.element_lengths).cumsum()
        rc = RangeCollection.from_breaks(
            breaks=self._mls_breaks, closed=self._closed)
        
        # To avoid rounding errors, enforce MLS length as the final endpoint
        try:
            rc.ends[-1] = self.mls_length
        except IndexError:
            pass
        return rc
    
    def _define_rte_ranges(self):
        """
        Generate range collection for provided location references.
        """
        rc = RangeCollection.from_breaks(
            breaks=self.rte_breaks, closed=self._closed, sort=False)
        if not rc.num_ranges == self.mls_ranges.num_ranges:
            raise ValueError("Input reference breaks must define a number of \
ranges equal to the number of line segments in the input multilinestring.")
        return rc
    
    def copy(self, deep=False):
        """
        Create an exact copy of the MLS route object instance.
        """
        if deep:
            return copy.deepcopy(self)
        else:
            return copy.copy(self)
        
    def locate_mls(self, loc, normalized=False, choose='first',
                   bounded=False):
        """
        Get the range index and the proportional distance along that range
        of the input MLS location.
        
        Parameters
        ----------
        
        ...
        bounded : boolean, default False
            Whether to raise an error when the location information falls
            outside the minimum and maximum bounds of the MLS range. If False,
            negative loc values will be snapped to 0 and loc values greater 
            than mls_length will be snapped to mls_length. If True, a 
            ValueError will be raised for values which fall outside of this 
            range.
        """
        # Convert normalized values to MLS values
        if normalized:
            loc = loc * self.mls_length
            
        # Validate input
        if loc < 0:
            if bounded:
                raise ValueError("Location value cannot be negative when \
the bounded parameter is True. Change to False to snap negative values to \
zero.")
            else:
                loc = 0
        elif loc > self.mls_length:
            if bounded:
                raise ValueError("Location value cannot be greater than the \
total length of the MLS when the bounded parameter is True. Change to False \
to snap negative values to the total length of the MLS.")
            else:
                loc = self.mls_length
        
        # Compute and return the index and proportional distance
        return self.mls_ranges.locate(loc, choose=choose)
        
    def locate_rte(self, loc, normalized=False, choose='first', snap=None):
        """
        Get the range index and the proportional distance along that range
        of the input route location.

        Parameters
        ----------
        snap : {None, 'near', 'left', 'right'}, default None
            If the input location does not fall within any ranges, snap to the 
            nearest match based on distance, choosing the closest range to the 
            left, right, or either side ('near'). If None, a value error will 
            be raised when no intersecting ranges are found.
        """
        # Convert normalized values to MLS values
        if normalized:
            loc = loc * self.mls_length
            # Compute and return the index and proportional distance
            return self.mls_ranges.locate(loc, choose=choose, snap=snap)
        else:
            # Compute and return the index and proportional distance
            return self.rte_ranges.locate(loc, choose=choose, snap=snap)
    
    def normalize(self, loc, by_mls=False, snap=None, **kwargs):
        """
        Normalize a location as an actual route location or the absolute 
        distance along the route's MultiLineString.
        
        Parameters
        ----------
        loc : numerical
            The distance along the route which will be normalized. Can be 
            route location or MultiLineString distance.
        by_mls : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of the actual cumulative length of the route's 
            MultiLineString. If False, interpret as route location. If True, 
            interpret as MLS location.
        snap : {None, 'near', 'left', 'right'}, default None
            If the input location does not fall within any ranges, snap to the 
            nearest match based on distance, choosing the closest range to the 
            left, right, or either side ('near'). If None, a value error will 
            be raised when no intersecting ranges are found.
        """
        # Convert to MLS if required
        if not by_mls:
            loc = self.convert_to_mls(
                loc, normalized=False, snap=snap, **kwargs)
        # Normalize location
        res = loc / self.mls_length
        return res
    
    def convert(self, mls_loc=None, rte_loc=None, choose='first'):
        """
        Convert an mls location to a reference location or vice versa.
        """
        if not mls_loc is None:
            return self.convert_to_rte(mls_loc, choose=choose)
        elif not rte_loc is None:
            return self.convert_to_mls(rte_loc, choose=choose)
        else:
            raise ValueError("No locator inputs provided.")
        
    def convert_to_rte(self, loc=None, normalized=False, choose='first',
                       bounded=False):
        """
        Convert an MLS or normalized reference location to a route location.
        
        Parameters
        ----------
        loc : numerical
            The location along the route in terms of the absolute distance 
            along the route's MultiLineString.
        normalized : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of proportional distance along the route. If False, the 
            location along the route will be interpreted normally.
        choose : {'first', 'last', 'all'}, default 'first'
            Which range to return information for if multiple ranges are found 
            which intersect with the provided location.
        bounded : boolean, default False
            Whether to raise an error when the location information falls
            outside the minimum and maximum bounds of the MLS range. If False,
            negative loc values will be snapped to 0 and loc values greater 
            than mls_length will be snapped to mls_length. If True, a 
            ValueError will be raised for values which fall outside of this 
            range.
        """
        # Locate the reference value on the route
        reference = self.locate_mls(loc=loc, normalized=normalized, 
                                    choose=choose, bounded=bounded)
        return self.rte_ranges.project(*reference)
        
    def convert_to_mls(self, loc=None, normalized=False, choose='first',
                       snap=None):
        """
        Convert a route or normalized reference location to an MLS location.
        
        Parameters
        ----------
        loc : numerical
            The location along the route in terms of route's defined location 
            values.
        normalized : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of proportional distance along the route. If False, the 
            location along the route will be interpreted normally.
        choose : {'first', 'last', 'all'}, default 'first'
            Which range to return information for if multiple ranges are found 
            which intersect with the provided location.
        snap : {None, 'near', 'left', 'right'}, default None
            If the input location does not fall within any ranges, snap to the 
            nearest match based on distance, choosing the closest range to the 
            left, right, or either side ('near'). If None, a value error will 
            be raised when no intersecting ranges are found.
        """
        # Locate the mls value on the route
        reference = self.locate_rte(loc=loc, normalized=normalized,
                                    choose=choose, snap=snap)
        return self.mls_ranges.project(*reference)
        
    def project(self, obj, by_mls=False, normalized=False):
        """
        Find the location along the route to a point nearest the input object. 
        This can be done using a normalized proportional distance along the 
        route, or the distance along the route in terms of route location or 
        MultiLineString absolute length.
        
        Parameters
        ----------
        obj : shapely geometry object
            A shapely geometry object to be projected along the route.
        by_mls : boolean, default False
            Whether to return the projected distance along the route in terms 
            of the actual cumulative length of the route's MultiLineString. If 
            False, interpret as route locations. If True, interpret as MLS 
            location. If the normalized parameter is True, this will be 
            superseded and proportional distance will be used.
        normalized : boolean, default False
            Whether to return the projected distance in terms of proportional 
            distance along the route. If False, the distance along the route 
            will be returned according to the by_mls parameter.
        """
        # Project along the MultiLineString
        loc = self.mls.project(obj, normalized=True)
        # Convert to requested projection
        if normalized:
            return loc
        else:
            if by_mls:
                return self.convert_to_mls(loc=loc, normalized=True)
            else:
                return self.convert_to_rte(loc=loc, normalized=True)
            
    def interpolate(self, loc, by_mls=False, normalized=False, snap=None, 
            **kwargs):
        """
        Return a point at the specified location along the route. This can be 
        done using a normalized proportional distance along the route, or the 
        distance along the route in terms of route location or MultiLineString 
        absolute length.

        Parameters
        ----------
        loc : numerical
            The distance along the route at which to create the point. Can be 
            proportional distance, route location, or MultiLineString 
            distance.
        by_mls : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of the actual cumulative length of the route's 
            MultiLineString. If False, interpret as route locations. If True, 
            interpret as MLS location. If the normalized parameter is True, 
            this will be superseded and proportional distance will be used.
        normalized : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of proportional distance along the route. If False, the 
            location along the route will be interpreted according to the 
            by_mls parameter.
        snap : {None, 'near', 'left', 'right'}, default None
            If the input location does not fall within any ranges, snap to the 
            nearest match based on distance, choosing the closest range to the 
            left, right, or either side ('near'). If None, a value error will 
            be raised when no intersecting ranges are found.
        """
        # Convert to mls reference
        if normalized:
            loc = self.convert_to_mls(loc, normalized=True, snap=snap)
        elif not by_mls:
            loc = self.convert_to_mls(loc, normalized=False, snap=snap)
        # Interpolate along the MultiLineString
        point = self.mls.interpolate(loc, normalized=False)
        return point
    
    def cut(self, beg, end, by_mls=False, normalized=False):
        """
        Cut the MLS route at the given begin and end points. This can be done 
        in terms of the route measure information (by_mls=False), in terms of
        MultiLineString actual cumulative length (by_mls=True), or in terms of 
        proportional distances along the route (normalized=True).
        
        Parameters
        ----------
        beg : float
            The location value at which the new route should begin.
        end : float
            The location value at which the new route should end.
        by_mls : boolean, default False
            Whether to interpret the begin and end points in terms of the 
            actual cumulative length of the route's MultiLineString. If False,
            interpret as route locations. If True, interpret as MLS locations. 
            If the normalized parameter is True, this will be superseded and 
            proportional distance will be used.
        normalized : boolean, default False
            Whether to interpret the begin and end points in terms of 
            proportional distances along the route. If False, the begin and 
            end points will be interpreted according to the by_mls parameter.
        
        Returns
        -------
        route : MLSRoute
            A new MLSRoute object instance with route information and a
            MultiLineString which has been cut according to the given 
            parameters.
        """
        if normalized:
            return self.cut_mls(beg, end, normalized=True)
        else:
            if by_mls:
                return self.cut_mls(beg, end, normalized=False)
            else:
                return self.cut_rte(beg, end, normalized=False)
            
    def cut_rte(self, beg, end, normalized=False):
        """
        Cut the MLS route at the given begin and end points in terms of the 
        route measure information or in terms of proportional distances along 
        the route (normalized=True).
        
        Parameters
        ----------
        beg : float
            The location value at which the new route should begin.
        end : float
            The location value at which the new route should end.
        normalized : boolean, default False
            Whether to interpret the begin and end points in terms of 
            proportional distances along the route. If False, the begin and 
            end points will be interpreted based on route measure information.
        
        Returns
        -------
        route : MLSRoute
            A new MLSRoute object instance with route information and a
            MultiLineString which has been cut according to the given 
            parameters.
        """
        # Convert to MLS locations
        beg = self.convert_to_mls(loc=beg, normalized=normalized,
                                  choose='first', snap='right')
        end = self.convert_to_mls(loc=end, normalized=normalized,
                                  choose='first', snap='left')
        
        # Cut based on MLS locations
        return self.cut_mls(beg, end, normalized=False)
    
    def cut_mls(self, beg, end, normalized=False):
        """
        Cut the MLS route at the given begin and end points in terms of the 
        MultiLineString actual cumulative length or in terms of proportional 
        distances along the route (normalized=True).
        
        Parameters
        ----------
        beg : float
            The location value at which the new route should begin.
        end : float
            The location value at which the new route should end.
        normalized : boolean, default False
            Whether to interpret the begin and end points in terms of 
            proportional distances along the route. If False, the begin and 
            end points will be interpreted based on MLS cumulative length.
        
        Returns
        -------
        route : MLSRoute
            A new MLSRoute object instance with route information and a
            MultiLineString which has been cut according to the given 
            parameters.
        """
        # Validate input
        try:
            # Ensure positive numeric values
            beg = max(float(beg), 0)
            end = max(float(end), 0)
        except:
            raise ValueError("Invalid begin or end input values.")
        
        # Convert normalized values to MLS values
        if normalized:
            beg = beg * self.mls_length
            end = end * self.mls_length
            
        # Interpolate begin point and compute range index of begin point
        if not beg is None:
            beg_point = self.interpolate(beg, by_mls=True, 
                                         normalized=False).coords[0]
            beg_index, beg_dist = self.mls_ranges.locate(loc=beg,
                             choose='last', closed='both', snap='right')
            beg_loc = self.rte_ranges.project(beg_index, beg_dist)
        else:
            beg_point = self.mls[0].coords[0]
            beg_index = 0
            beg_loc = self.rte_ranges.begs[0]

        # Interpolate end point and compute range index of end point
        if not end is None:
            end_point = self.interpolate(end, by_mls=True, 
                                         normalized=False).coords[0]
            end_index, end_dist = self.mls_ranges.locate(loc=end,
                             choose='first', closed='both', snap='left')
            end_loc = self.rte_ranges.project(end_index, end_dist)
        else:
            end_point = self.mls[-1].coords[-1]
            end_index = self.mls_ranges.num_ranges - 1
            end_loc = self.rte_ranges.ends[-1]
        
        # Unique case: begin and end points both fall between the same two
        # vertices
        if beg_index == end_index:
            mls = MultiLineString([LineString([beg_point, end_point])])
            breaks = [[beg_loc, end_loc]]
            return MLSRoute(mls, rte_breaks=breaks, closed=self.closed)
        
        # Construct new MultiLineString based on new begin and end points
        total_size = 0
        lines = []
        breaks = []
        
        # Iterate over the LineStrings in the MLS
        for num, (line, breaks_all) in enumerate(zip(self.mls,
                 self.rte_breaks)):
            
            # Get the number of ranges in the LineString
            points_all = list(line.coords)
            size = len(points_all)
            
            # Compute the start slicing parameter if the LineString is to be 
            # included
            if beg_index >= total_size + size - 1:
                # Not included, upstream of cut: skip
                total_size += size - 1
                continue
            elif beg_index >= total_size:
                # Included: cut within line
                i = beg_index - total_size + 1
            else:
                # Included: not cut within line
                i = None
                    
            # Compute the stop slicing parameter if the LineString is to be 
            # included
            if end_index < total_size:
                # Not included, downstream of cut: break
                break
            elif end_index < total_size + size - 1:
                # Included: cut within line
                j = end_index - total_size + 1
            else:
                # Included: not cut within line
                j = None
            
            # Collect the valid points based on slicing computations
            if i is None:
                points_select = []
                breaks_select = []
            else:
                points_select = [beg_point]
                breaks_select = [beg_loc]
            slicer = slice(i,j)
            points_select += points_all[slicer]
            breaks_select += breaks_all.tolist()[slicer]
            if j is None:
                lines.append(LineString(points_select))
                breaks.append(np.asarray(breaks_select))
                total_size += size - 1
                continue
            else:
                points_select += [end_point]
                breaks_select += [end_loc]
                lines.append(LineString(points_select))
                breaks.append(breaks_select)
                break
        
        # Create MLS route based on computed results
        mls = MultiLineString(lines)
        return MLSRoute(mls, rte_breaks=breaks, closed=self.closed)
    
    def segment(self, cuts, by_mls=False, normalized=False, **kwargs):
        """
        Cut the MLS Route into segments based on the given cut points.
        
        Parameters
        ----------
        cuts : array-like
            Array-like of numeric values representing the locations at which 
            to cut the route, either in terms of MultiLineString distance or 
            defined route locations.
        by_mls : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of the actual cumulative length of the route's 
            MultiLineString. If False, interpret as route locations. If True, 
            interpret as MLS location. If the normalized parameter is True, 
            this will be superseded and proportional distance will be used.
        normalized : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of proportional distance along the route. If False, the 
            location along the route will be interpreted according to the 
            by_mls parameter.
        
        Returns
        -------
        segments : list of MLSRoutes
            A list of new MLSRoute object instances, each with route 
            information and a MultiLineString which has been cut according to 
            the given parameters.        
        """
        # Validate inputs
        try:
            cuts = np.sort(np.asarray(cuts))
        except:
            raise ValueError("Must provide segment cuts as array-like of \
numeric cutting point values.")
        
        # Compute the valid ranges of the routes
        beg =  self.mls_ranges.begs.min() if by_mls \
                else self.rte_ranges.begs.min()
        end = self.mls_ranges.ends.max() if by_mls \
                else self.rte_ranges.ends.max()

        # Iterate over cut points
        segments = []
        for beg_i, end_i in zip(cuts[:-1], cuts[1:]):
            
            # Check for valid location
            if end_i < beg or beg_i > end:
                continue
            
            # Perform cut
            segment_i = self.cut(beg_i, end_i, by_mls=by_mls, 
                                 normalized=normalized)
            # Append new segment to the list of created segments
            segments.append(segment_i)
        
        return segments

    def snap(self, loc, by_mls=False, normalized=False):
        """
        Snap a provided location value to the bounds of the route based on the 
        provided parameters. If the location falls within the bounds of the 
        route, the same value will be returned.

        Parameters
        ----------
        loc : scalar
            Location value to snap to the route bounds.
        by_mls : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of the actual cumulative length of the route's 
            MultiLineString. If False, interpret as route location. If True, 
            interpret as MLS location.
        normalized : boolean, default False
            Whether to interpret the provided location along the route in 
            terms of proportional distance along the route. If False, the 
            location along the route will be interpreted according to the 
            by_mls parameter.
        """
        # Snap location by selected range collection
        if normalized:
            return max(min(loc, 1), 0)
        elif by_mls:
            return self.mls_ranges.snap(loc)
        else:
            return self.rte_ranges.snap(loc)
    
    def bearing(self, positive=True, invert=False):
        """
        Approximate the bearing angle of the route, based on the first and 
        last points in the route's MLS.
        
        Parameters
        ----------
        positive : bool, default True
            Whether to enforce a positive range on the computed bearing angle. 
            If True, the bearing angle will fall on the range [0,360). If 
            False, the bearing angle will fall on the range (-180,180].
        invert : bool, default False
            Whether to invert the computed bearing angle, effectively 
            reversing the direction of the route.
        """
        # Capture x and y distance between points
        x_diff = self.mls[-1].xy[0][-1] - self.mls[0] .xy[0][0]
        y_diff = self.mls[-1].xy[1][-1] - self.mls[0] .xy[1][0]
        
        # Compute bearing angle
        bearing = math.degrees(math.atan2(y_diff, x_diff))
        
        # Invert if requested
        if invert:
            bearing += 180
        
        # Enforce range
        if positive and bearing < 0:
            bearing += 360
        elif not positive and bearing > 180:
            bearing -= 360
            
        return bearing


#####################
# SUPPORT FUNCTIONS #
#####################

def combine_mpgs(objs, cls=None):
    """
    Combine multiple multipart geometries into a single multipart geometry of 
    geometry collection.
    """
    # Generate new list of individual geometries
    new = []
    for obj in objs:
        if isinstance(obj, shapely.geometry.base.BaseMultipartGeometry):
            new.extend(list(obj))
        elif isinstance(obj, shapely.geometry.base.BaseGeometry):
            new.extend([obj])
        else:
            raise TypeError(f"Invalid geometry type")
    # Convert list to geometry collection or provided class
    if cls is None:
        new = shapely.geometry.collection.GeometryCollection(new)
    else:
        new = cls(new)
    return new

def _distribute_dimensions(mls, beg, end):
    # Validate input
    if not isinstance(mls, MultiLineString):
        raise ValueError('Input MLS must be MultiLineString type.')
    # Compute dimensions
    delta = end - beg
    lengths = np.array([ls.length for ls in mls])
    proportions = np.cumsum(lengths / lengths.sum() * delta)
    begs = np.insert(proportions[:-1] + beg, 0, beg)
    ends = proportions + beg
    # Return proportions
    return begs, ends
    

# Sample use
if __name__ == '__main__':
    # Create a generic MLS
    mls = MultiLineString([[(0,0), (0,5), (5,5), (5,0)],
                           [(5,0), (5,-5), (10,-5), (10,0)],
                           [(10,0), (10,5), (15,5), (15,0)],
                           [(20,0), (20,-5), (25,-5), (25,0)]])                
                
    # Create a generic range set
    rte_ranges = [(0,150), (200,350), (400,550), (600,650)]
    
    # Create a MLS route
    route = MLSRoute(mls, rte_ranges=rte_ranges)
    
    # Cut the sample route
    test = route.cut_mls(0,0.80, True)
        
        