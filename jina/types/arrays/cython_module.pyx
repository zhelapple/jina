cdef class Foo:
    cdef int bar
    def __init__(self):
        print(f' creating foo')
        self.bar = 4

    def call(self):
        print(f' calling {self.bar}')