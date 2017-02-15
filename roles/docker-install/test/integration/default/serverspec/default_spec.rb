require 'serverspec'

set :backend, :exec

# Verify that the trusted CA cert is installed

describe file ('/usr/bin/docker') do
  it {should exist}
  it {should be_mode 755}
end
