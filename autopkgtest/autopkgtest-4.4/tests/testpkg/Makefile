build:
	/bin/echo -e "#!/bin/sh -e\necho built script OK" > test_built
	/bin/echo -e "#!/bin/sh -e\nexec $(PWD)/test_built" > test_abspath
	chmod 755 test_built test_abspath

clean:
	rm -f test_built

distclean: clean

install: build
	install -D -m755 test_static $(DESTDIR)/usr/bin/test_static
	install -D -m755 test_built $(DESTDIR)/usr/bin/test_built
