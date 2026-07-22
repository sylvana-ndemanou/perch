.PHONY: build run test install

build:
	swift build

run:
	swift run Perch

test:
	swift test

install:
	./Scripts/install.sh
