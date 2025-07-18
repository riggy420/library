document: 
	python document.py

website: 
	(\
	. webpage/bin/activate;  \
	python app.py; \
	)

main:
	python risk_assessment_library.py

test:
	python test_out.py

var ?= America

update:
	python scrapper.py $(var) $(var2)