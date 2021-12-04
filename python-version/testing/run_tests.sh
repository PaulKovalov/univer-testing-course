#!/bin/sh
# First step is running unit tests defined in the python test file.
python3 -m pytest

# Integration testing
# ID: 7
test_password="Qwerty123"
expected_storage_path="/home/$USER/.pmp/81d1d68e2230674aa504d7fa2efaa8b893a128d3cc477385f26fa106380fb004.pst"
echo $'-i\n'$test_password | python3 pm.py
if ! [ -f $expected_storage_path ]
then
  echo "File $expected_storage_path doesn't exist"
  # 1-255 exit code means failure.
  exit 1
fi
expected_file_content="77aae185203edc6357676db95caa25d0f398d402c1723e6a7b42cfe8d2967f2e"
if [ $expected_file_content != $(cat $expected_storage_path) ]
then
  echo "Expected $expected_file_content but got $(cat $expected_storage_path)"
  exit 1
fi

# User friendly
# ID: 10
output=$(echo "abracadabra" | python3 pm.py)
want_substr="Unexpected command:"
if [[ "$output" != *"$want_substr"* ]];
then
  echo "Expected substring $want_substr to be in $output, but it wasn't"
  exit 1
fi

# 0 exit code indicates all tests have passed successfully
exit 0
