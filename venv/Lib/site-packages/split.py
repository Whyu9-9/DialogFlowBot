"""Functions to split or partition sequences."""

import collections
import itertools
import operator
from platform import python_version_tuple

__all__ = [ "chop", "groupby", "partition", "split" ]
__author__ = "Sergey Astanin"
__license__ = "MIT"
__version__ = "0.4"

if python_version_tuple()[0] == "2":
    _range = xrange
    _imap = itertools.imap
else:
    _range = range
    _imap = map

def groupby(predicate, sequence, predicate_values=()):
    """
    Split a sequence into subsequences with the same predicate value
    on all elements. Return an iterator over pairs of
    (predicate_value, subsequence_iterator).

    Arguments:

    predicate         a function on sequence elements
    sequence          original sequence
    predicate_values  if given, build subsequences only for these
                      values of the predicate function

    Unlike itertools.groupby, return only one subsequence' iterator
    per predicate value; argument order is reversed to match other
    functions in this module.

    >>> [(k, list(i)) for k,i in groupby(lambda x: x%3, range(7))]
    [(0, [0, 3, 6]), (1, [1, 4]), (2, [2, 5])]

    This function is lazy and consumes sequence only on demand, but to
    build the comlete list of predicate values it needs to scan the
    entire sequence. To avoid such an eager behaviour, the function
    can take a list of possible predicate_values in advance.

    Working with a really long sequence:

    >>> if python_version_tuple()[0] > '2': xrange=range
    >>> gs = groupby(lambda x: x%3, xrange(int(1e9)), predicate_values=(0,1,2))
    >>> d = dict(gs)
    >>> list(itertools.takewhile(lambda x: x < 20, d[1]))
    [1, 4, 7, 10, 13, 16, 19]

    """
    queues = collections.defaultdict(collections.deque)
    kvs = _imap(lambda v: (predicate(v), v), sequence)
    kvs, kvs2 = itertools.tee(kvs, 2)
    def uniqkeys():
        keys = set()
        for k, v in kvs:
            if not (k in keys):
                keys.add(k)
                yield k
    def subsequence(k):
        while True:
            queued = queues[k]
            if queued:
                yield queued.popleft()
            else:
                k2, v2 = next(kvs2)
                queues[k2].append(v2)
    pvals =  uniqkeys() if not predicate_values else predicate_values
    return _imap(lambda k: (k, subsequence(k)), pvals)

# partition can be implemented in terms of groupyby, in just two lines
# of code, but it appears to be twice as slow

class _SubSequencer:
    """
    Lazily process a sequence in single pass and split into many.
    Compute all output sequences even if only one of them is consumed.
    Maintain as many subsequence queues as there are predicate values.
    """
    def __init__(self, predicate, sequence):
        self.predicate = predicate
        self.subseqs = dict()  # mapping of { predicate_value: subseq }
        self.seq = iter(sequence)

    def _subqueue(self, predicate_value):
        "Get or create a subsequence queue."
        if not predicate_value in self.subseqs:
            subseq = self.subseqs[predicate_value] = collections.deque([])
        else:
            subseq = self.subseqs[predicate_value]
        return subseq

    def _subappend(self, predicate_value, item):
        "Append a processed item to subsequence queue."
        subseq = self._subqueue(predicate_value)
        subseq.append(item)

    def subnext(self, predicate_value):
        "Next value in the subsequence corresponding to predicate_value."
        subseq = self._subqueue(predicate_value)
        if subseq:
            return subseq.popleft()
        else:  # subsequence queue is empty
            while True:  # exit on StopIteration
                n = next(self.seq)
                pv = bool(self.predicate(n))  # support overridden __bool__()
                if pv == predicate_value:
                    return n
                else:
                    self._subappend(pv, n)

def partition(condition, sequence):
    """
    Split a sequence into two subsequences, in single-pass and preserving order.

    Arguments:

    condition   a function; if condition is None, split true and false items
    sequence    an iterable object

    Return a pair of generators (seq_true, seq_false). The first one
    builds a subsequence for which the condition holds, the second one
    builds a subsequence for which the condition doesn't hold.

    As the function works in single pass, it leads to build-up of both
    subsequences even if only one of them is consumed.

    It is similar to Data.List.partition in Haskell, or running two
    complementary filters:

       from itertools import ifilter, ifilterfalse
       (ifilter(condition, sequence), ifilterfalse(condition, sequence))

    >>> def odd(x): return x%2 != 0
    >>> odds, evens = partition(odd, range(10))
    >>> next(odds)
    1
    >>> next(odds)
    3
    >>> list(evens)
    [0, 2, 4, 6, 8]
    >>> list(odds)
    [5, 7, 9]

    >>> class IsOdd(object): # objects with overloaded bool()
    ...     def __init__(self, x):
    ...         self.x = x
    ...     def __bool__(self):     # Python 3
    ...         return self.x % 2 != 0
    ...     def __nonzero__(self):  # Python 2
    ...         return self.x % 2 != 0
    ...
    >>> odds, evens = partition(lambda v: IsOdd(v), range(3))
    >>> list(odds)
    [1]
    >>> list(evens)
    [0, 2]

    """
    cond = condition if condition else bool  # eval as bool if condition is None
    ss = _SubSequencer(cond, sequence)
    def condition_holds():
        while True:
            yield ss.subnext(True)
    def condition_doesnt_hold():
        while True:
            yield ss.subnext(False)
    return condition_holds(), condition_doesnt_hold()

def _take(n, sequence):
    """Take the first n elements of the sequence.
    Return head and tail sequences.

    >>> head, tail = _take(3, range(10))
    >>> list(head), list(tail)
    ([0, 1, 2], [3, 4, 5, 6, 7, 8, 9])

    >>> head, tail = _take(13, range(10))
    >>> list(head), list(tail)
    ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [])
    """
    head = []
    xs = iter(sequence)
    try:
        for i in _range(n):
            x = next(xs)
            head.append(x)
        return head, xs
    except StopIteration:
        return head, ()

def chop(n, sequence, truncate=False):
    """
    Split a sequence into chunks of size n.
    Return an iterator over chunks.

    Arguments:

    n           chunk size
    sequence    an iterable object
    truncate    if True, truncate sequence length to the multiple of n;
                if False, the size of last chunk may be less than n.

    It is similar to partition and partition-all in Clojure.

    >>> list(chop(3, range(10)))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]
    >>> list(chop(3, range(10), truncate=True))
    [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    >>> list(chop(3, range(6)))
    [[0, 1, 2], [3, 4, 5]]
    >>> list(chop(1, range(3)))
    [[0], [1], [2]]

    This function is lazy and produces new chunks only on demand:

    >>> if python_version_tuple()[0] > '2': xrange=range
    >>> chunks = chop(3, xrange(int(1e9)))
    >>> next(chunks)
    [0, 1, 2]

    """
    assert n >= 1, "chunk size is not positive"
    def chopper():
        tail = sequence
        while tail:
            head, tail = _take(n, tail)
            if head and (not truncate or len(head) == n):
                yield head
    return chopper()

def _nextByDelim(delimfunc, seq):
    "Next chunk from from the sequence seq, and sequence tail."
    iseq = iter(seq)
    chunk = []
    try:
        while True:
            x = next(iseq)
            if not delimfunc(x):
                chunk.append(x)
            else:
                break
        return chunk, iseq
    except StopIteration:
        return chunk, ()

def split(delimiter, sequence, maxsplit=None):
    """
    Break a sequence on particular elements.
    Return an iterator over chunks (delimiters excluded).

    Arguments:

    delimiter   if a function, it returns True on chunk separators;
                otherwise, it is the value of chunk separator.
    sequence    original sequence;
    maxsplit    if given, at most maxsplit splits are done.

    >>> list(split(0, [1,2,3,0,4,5,0,0,6]))
    [[1, 2, 3], [4, 5], [], [6]]

    >>> list(map(list, split(0, [1,2,3,0,4,5,0,0,6], maxsplit=2)))
    [[1, 2, 3], [4, 5], [0, 6]]

    >>> list(split(lambda x: x==5, range(10)))
    [[0, 1, 2, 3, 4], [6, 7, 8, 9]]

    This function is lazy and produces new chunks only on demand:

    >>> if python_version_tuple()[0] > '2': xrange=range
    >>> chunks = split(9, xrange(int(1e9)))
    >>> next(chunks)
    [0, 1, 2, 3, 4, 5, 6, 7, 8]

    """
    if hasattr(delimiter, "__call__"):
        delimfunc = delimiter
    else:
        delimfunc = lambda x: x == delimiter
    def splitter():
        tail = sequence
        splits = 0
        while tail:
            if maxsplit and splits >= maxsplit:
                yield tail
                tail = None
            else:
                chunk, tail = _nextByDelim(delimfunc, tail)
                splits += 1
                yield chunk
    return splitter()

if __name__ == "__main__":
    import doctest
    doctest.testmod()
