#!/bin/sh

export black="0;30"
export dark_gray="1;30"
export red="0;31"
export light_red="1;31"
export green="0;32"
export light_green="1;32"
export orange="0;33"
export yellow="1;33"
export blue="0;34"
export light_blue="1;34"
export purple="0;35"
export light_purple="1;35"
export cyan="0;36"
export light_cyan="1;36"
export light_gray="0;37"
export white="1;37"

color_echo_no_crlf(){
  echo -ne "\e[$1m$2\e[0m"
}

color_echo(){
  color_echo_no_crlf $1 "$2"
  echo
}

export roles_path="`pwd`/roles"
export changed_roles=`ls $roles_path`
exit_status=0
run_kitchen_tests(){
  role_name="$1"
  role_path="$roles_path/$role_name"
  kitchen_list="kitchen list"
  kitchen_test="kitchen test centos"
  color_echo_no_crlf $orange "Role: "
  color_echo $green "$role_name"
  color_echo_no_crlf $orange "Path: "
  color_echo $green "$role_path"
  cd $role_path
  kitchen list
  kitchen test centos
}

print_roles(){
  color_echo $orange "Roles:"
  color_echo $orange "-------------"
  for role in $changed_roles
  do
    color_echo $green "  - $role"
  done
  echo
}

run_all_kitchen_tests(){
  color_echo $orange "Running kitchen tests:"
  color_echo $orange "---------------------"
  echo "Test Report - Exit Status" > output.log
  for role in  $changed_roles
  do
    run_kitchen_tests $role
    code=$?
    exit_status=$((exit_status+code))
    echo "$role - $code" >> ../../output.log
  done
}

print_roles
run_all_kitchen_tests
exit $exit_status
