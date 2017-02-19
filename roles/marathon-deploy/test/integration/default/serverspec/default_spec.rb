require 'serverspec'

set :backend, :exec

describe command ('which curl') do
  its(:stdout) {should contain('bin')}
end

